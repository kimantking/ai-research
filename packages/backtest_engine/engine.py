"""이벤트 드리븐 백테스트 엔진.

★ 설계 원칙 (§17, Point-in-Time)
   1) 엔진이 시간을 한 봉씩 전진시킵니다.
   2) 전략에게는 **T 시점까지의 시리즈만** 넘깁니다.
      미래 봉은 인자로 전달되지 않으므로 볼 방법이 없습니다.
   3) 신호는 T 종가에 나오고, 체결은 **T+1 시가**에 이뤄집니다.
      같은 봉의 종가에 체결하면 그것만으로 이미 미래를 쓴 것입니다.
      (이 한 줄 때문에 수많은 백테스트가 거짓말을 합니다)
   4) 수수료와 슬리피지를 반영합니다.

LEAN(Apache-2.0) 의 '엔진이 시간을 전진시키고 전략은 현재까지만 본다'는
구조를 참고했지만, 코드는 병합하지 않았습니다 (docs/LICENSE_AUDIT.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from packages.chart_skills.series import OHLCV

from .metrics import performance_metrics

Side = Literal["LONG", "FLAT"]


@dataclass
class Signal:
    """전략이 내는 신호. 현금 비중 0.0~1.0."""
    target_weight: float = 0.0
    reason: str = ""

    def __post_init__(self):
        if not 0.0 <= self.target_weight <= 1.0:
            raise ValueError("target_weight 는 0.0~1.0 이어야 합니다 (공매도·레버리지 미지원)")


@dataclass
class Fill:
    index: int
    ts: int
    price: float
    weight_before: float
    weight_after: float
    cost: float
    reason: str


@dataclass
class BacktestResult:
    equity: list[float] = field(default_factory=list)
    returns: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    trade_returns: list[float] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    warmup: int = 0
    leak_guard: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "fills": len(self.fills),
            "trades": len(self.trade_returns),
            "warmup_bars": self.warmup,
            "final_equity": round(self.equity[-1], 4) if self.equity else None,
            "leak_guard": self.leak_guard,
            "equity_curve": [round(x, 4) for x in self.equity],
        }


# 전략 시그니처: (past_only_series, current_weight) -> Signal
Strategy = Callable[[OHLCV, float], Signal]


class BacktestEngine:
    def __init__(
        self,
        commission_bps: float = 5.0,      # 편도 0.05%
        slippage_bps: float = 5.0,        # 편도 0.05%
        initial_equity: float = 100_000.0,
        warmup: int = 60,
        exchange: str | None = None,      # "XNYS" 등. None 이면 캘린더 검사 안 함
    ):
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.initial_equity = initial_equity
        self.warmup = warmup
        self.exchange = exchange

    # ------------------------------------------------------------------
    def _calendar_check(self, series: OHLCV) -> dict:
        """★ 'T+1 봉' 이 정말 '다음 거래일' 인지 확인합니다.

        이 엔진은 series[t+1] 을 체결 봉으로 씁니다.
        시계열이 실제 거래일만 담고 있으면 그것이 곧 다음 거래일입니다.
        그러나 주말 봉이 섞여 있거나(합성 데이터) 중간이 비어 있으면
        'T+1' 의 의미가 조용히 달라집니다. 그래서 **말해줍니다.**
        """
        if not self.exchange:
            return {
                "checked": False,
                "reason": "exchange 를 지정하지 않았습니다 (봉 인덱스 기준으로 계산)",
                "trustworthy": False,
            }
        try:
            from packages.market_calendar import SessionClock
        except Exception as exc:                     # pragma: no cover
            return {"checked": False, "reason": f"캘린더 모듈 없음: {exc}",
                    "trustworthy": False}

        clock = SessionClock.from_timestamps([c.ts for c in series], self.exchange)
        summary = clock.summary()
        aligned = summary["aligned_to_sessions"] and summary["missing_sessions"] == 0
        return {
            "checked": True,
            "exchange": summary["exchange"],
            "aligned_to_sessions": summary["aligned_to_sessions"],
            "non_session_bars": summary["non_session_bars"],
            "missing_sessions": summary["missing_sessions"],
            "trustworthy": aligned,
            "reason": (
                "모든 봉이 실제 거래일이고 빠진 거래일도 없습니다. "
                "T+1 봉 = 다음 거래일."
                if aligned else
                "봉이 실제 거래일과 일치하지 않습니다. "
                "'T+1 봉' 을 '다음 거래일' 로 해석하면 안 됩니다."
            ),
        }

    # ------------------------------------------------------------------
    def run(
        self,
        series: OHLCV,
        strategy: Strategy,
        benchmark: OHLCV | None = None,
        periods_per_year: int = 252,
    ) -> BacktestResult:
        n = len(series)
        if n < self.warmup + 3:
            raise ValueError(f"데이터가 너무 짧습니다 (필요 {self.warmup + 3}봉, 실제 {n}봉)")

        equity = self.initial_equity
        weight = 0.0
        eq_curve: list[float] = []
        weights: list[float] = []
        fills: list[Fill] = []
        trade_returns: list[float] = []
        entry_price: float | None = None

        # ★ 누수 감시: 전략에게 넘어간 시리즈의 마지막 봉 인덱스를 기록합니다.
        max_index_seen = -1
        pending: Signal | None = None

        for t in range(self.warmup, n - 1):
            # --- 1) T 시점: 전략은 '과거만' 봅니다 ---
            past = series[: t + 1]           # 미래 봉은 아예 넘어가지 않습니다
            max_index_seen = max(max_index_seen, t)
            sig = strategy(past, weight)
            if not isinstance(sig, Signal):
                raise TypeError("전략은 Signal 을 돌려줘야 합니다")

            # --- 2) T+1 시가에 체결 ---
            nxt = series[t + 1]
            if abs(sig.target_weight - weight) > 1e-9:
                direction = 1 if sig.target_weight > weight else -1
                slip = 1 + direction * self.slippage_bps / 10_000.0
                fill_price = nxt.open * slip
                turnover = abs(sig.target_weight - weight)
                cost = equity * turnover * (self.commission_bps / 10_000.0)
                equity -= cost

                if weight == 0.0 and sig.target_weight > 0:
                    entry_price = fill_price
                elif sig.target_weight == 0.0 and entry_price:
                    trade_returns.append((fill_price - entry_price) / entry_price)
                    entry_price = None

                fills.append(Fill(index=t + 1, ts=nxt.ts, price=fill_price,
                                  weight_before=weight, weight_after=sig.target_weight,
                                  cost=cost, reason=sig.reason))
                weight = sig.target_weight

            # --- 3) T+1 종가로 평가 ---
            bar_ret = (nxt.close - nxt.open) / nxt.open if nxt.open else 0.0
            if t > self.warmup:
                prev = series[t]
                overnight = (nxt.open - prev.close) / prev.close if prev.close else 0.0
            else:
                overnight = 0.0
            period_ret = (1 + overnight) * (1 + bar_ret) - 1
            equity *= (1 + weight * period_ret)

            eq_curve.append(equity)
            weights.append(weight)

        rets = [
            (eq_curve[i] - eq_curve[i - 1]) / eq_curve[i - 1] if eq_curve[i - 1] else 0.0
            for i in range(1, len(eq_curve))
        ]

        bench_rets = None
        if benchmark is not None and len(benchmark) >= n:
            bc = benchmark.closes
            bench_rets = [
                (bc[i] - bc[i - 1]) / bc[i - 1] if bc[i - 1] else 0.0
                for i in range(self.warmup + 2, self.warmup + 2 + len(rets))
            ]
            if len(bench_rets) != len(rets):
                bench_rets = None

        result = BacktestResult(
            equity=eq_curve,
            returns=rets,
            weights=weights,
            fills=fills,
            trade_returns=trade_returns,
            warmup=self.warmup,
            metrics=performance_metrics(
                eq_curve, rets, bench_rets,
                periods_per_year=periods_per_year, trades=trade_returns,
            ),
            leak_guard={
                "max_bar_index_shown_to_strategy": max_index_seen,
                "last_bar_index": n - 1,
                "future_bars_never_shown": n - 1 - max_index_seen,
                "execution_rule": "신호는 T 종가, 체결은 T+1 시가",
                "note": (
                    "전략 함수에는 series[:t+1] 만 전달됩니다. "
                    "미래 봉은 인자로 존재하지 않으므로 볼 수 없습니다."
                ),
                "calendar": self._calendar_check(series),
            },
        )
        return result


# ====================================================================== 예시 전략


def sma_crossover_strategy(fast: int = 20, slow: int = 50) -> Strategy:
    """단순 이동평균 교차. '이런 모양이면 된다'를 보여주는 예시입니다.

    ※ 이 전략이 돈을 번다는 뜻이 아닙니다. 엔진 검증용입니다.
    """
    from packages.chart_skills.indicators import sma

    def strategy(past: OHLCV, current_weight: float) -> Signal:
        closes = past.closes
        f = sma(closes, fast)[-1]
        s = sma(closes, slow)[-1]
        if f is None or s is None:
            return Signal(0.0, "지표 준비 안 됨")
        if f > s:
            return Signal(1.0, f"SMA{fast} > SMA{slow}")
        return Signal(0.0, f"SMA{fast} <= SMA{slow}")

    return strategy


def buy_and_hold_strategy() -> Strategy:
    def strategy(past: OHLCV, current_weight: float) -> Signal:
        return Signal(1.0, "매수 후 보유")

    return strategy
