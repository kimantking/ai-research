"""성과 지표.

Phase 19 에서 QuantStats(Apache-2.0) 로 교체·검증할 수 있지만,
여기 구현은 '정답 대조용 기준값'으로 계속 남습니다.
외부 라이브러리를 못 쓰는 환경에서도 백테스트가 돌아가야 하기 때문입니다.
"""

from __future__ import annotations

import math
from typing import Sequence

TRADING_DAYS = 252


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float], ddof: int = 1) -> float:
    n = len(xs)
    if n <= ddof:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def max_drawdown(equity: Sequence[float]) -> tuple[float, int, int]:
    """최대 낙폭과 그 구간 (peak_index, trough_index)."""
    if not equity:
        return 0.0, 0, 0
    peak = equity[0]
    peak_i = 0
    worst = 0.0
    worst_peak = 0
    worst_trough = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak, peak_i = v, i
        dd = (v - peak) / peak if peak else 0.0
        if dd < worst:
            worst, worst_peak, worst_trough = dd, peak_i, i
    return worst, worst_peak, worst_trough


def linreg(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    """(기울기, 절편) — 알파/베타 계산용."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0
    mx, my = _mean(xs), _mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return slope, my - slope * mx


def performance_metrics(
    equity: Sequence[float],
    returns: Sequence[float] | None = None,
    benchmark_returns: Sequence[float] | None = None,
    risk_free_annual: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
    trades: Sequence[float] | None = None,
) -> dict:
    """자산곡선에서 표준 성과 지표를 계산합니다."""
    if len(equity) < 2:
        return {"error": "데이터 부족", "bars": len(equity)}

    if returns is None:
        returns = [
            (equity[i] - equity[i - 1]) / equity[i - 1] if equity[i - 1] else 0.0
            for i in range(1, len(equity))
        ]

    n = len(returns)
    total_return = equity[-1] / equity[0] - 1.0
    years = n / periods_per_year if periods_per_year else 0.0
    cagr = ((equity[-1] / equity[0]) ** (1 / years) - 1.0) if years > 0 and equity[0] > 0 else 0.0

    vol = _std(returns) * math.sqrt(periods_per_year)
    rf_per = risk_free_annual / periods_per_year
    excess = [r - rf_per for r in returns]
    sharpe = (_mean(excess) / _std(excess) * math.sqrt(periods_per_year)) if _std(excess) else 0.0

    downside = [min(0.0, r - rf_per) for r in returns]
    dstd = math.sqrt(sum(d * d for d in downside) / len(downside)) if downside else 0.0
    sortino = (_mean(excess) / dstd * math.sqrt(periods_per_year)) if dstd else 0.0

    mdd, peak_i, trough_i = max_drawdown(equity)
    calmar = (cagr / abs(mdd)) if mdd else 0.0

    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    win_rate = len(wins) / n if n else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss else (float("inf") if gross_win else 0.0)

    out = {
        "bars": len(equity),
        "total_return_pct": round(total_return * 100, 3),
        "cagr_pct": round(cagr * 100, 3),
        "volatility_pct": round(vol * 100, 3),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown_pct": round(mdd * 100, 3),
        "calmar": round(calmar, 3),
        "win_rate_pct": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else None,
        "drawdown_peak_index": peak_i,
        "drawdown_trough_index": trough_i,
    }

    if benchmark_returns is not None and len(benchmark_returns) == n:
        beta, alpha_per = linreg(list(benchmark_returns), list(returns))
        out["beta"] = round(beta, 4)
        out["alpha_annual_pct"] = round(alpha_per * periods_per_year * 100, 3)
        bench_total = 1.0
        for r in benchmark_returns:
            bench_total *= (1 + r)
        out["benchmark_return_pct"] = round((bench_total - 1) * 100, 3)
        out["excess_return_pct"] = round((total_return - (bench_total - 1)) * 100, 3)

    if trades:
        twins = [t for t in trades if t > 0]
        out["trades"] = len(trades)
        out["trade_win_rate_pct"] = round(len(twins) / len(trades) * 100, 2)
        out["avg_trade_pct"] = round(_mean(trades) * 100, 3)

    return out
