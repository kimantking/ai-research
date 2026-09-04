"""Pattern Miner — 조건 조합을 탐색하고, 과적합을 걸러냅니다.

★ 이 파일에서 제일 중요한 것은 '패턴을 찾는 코드'가 아니라
  '찾은 패턴을 믿지 않는 코드'입니다.

과적합 방지 (§40 / Phase 13)
    데이터를 시간 순으로 4등분합니다.
        TRAIN      → 여기서만 패턴을 '발견'합니다
        VALIDATION → 발견한 패턴을 1차 확인
        TEST(OOS)  → 마지막에 딱 한 번 확인
        WALK       → 순차 전진 검증
    같은 구간에서 발견하고 검증하는 것을 코드가 막습니다.

    무작위 분할이 아니라 '시간 분할'입니다.
    시계열을 무작위로 섞으면 미래가 과거에 섞여 들어갑니다.

승격 기준
    - 표본 수가 최소치 미만이면 STRONG 으로 인정하지 않습니다.
    - TRAIN 에서 좋았는데 VALIDATION/TEST 에서 무너지면 기각합니다.
    - 방향이 뒤집히면 기각합니다.
    "많이 찾는 것"이 목표가 아니라 "살아남는 것만 남기는 것"이 목표입니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Iterable, Sequence

from packages.chart_skills.indicators import (
    adx,
    atr,
    relative_volume,
    roc,
    rsi,
    sma,
)
from packages.chart_skills.series import OHLCV

from .statistics import (
    correct_multiple_tests,
    effective_sample_size,
    significance_report,
)
from .walkforward import walk_forward

# ====================================================================== 조건


@dataclass(frozen=True)
class Condition:
    name: str
    fn: Callable[[dict], bool]

    def __call__(self, ctx: dict) -> bool:
        try:
            return bool(self.fn(ctx))
        except (TypeError, KeyError):
            return False


def _get(ctx: dict, key: str):
    v = ctx.get(key)
    return None if v is None else v


CONDITIONS: list[Condition] = [
    Condition("RSI<30",        lambda c: _get(c, "rsi") is not None and c["rsi"] < 30),
    Condition("RSI>70",        lambda c: _get(c, "rsi") is not None and c["rsi"] > 70),
    Condition("RSI 40~60",     lambda c: _get(c, "rsi") is not None and 40 <= c["rsi"] <= 60),
    Condition("종가>SMA20",     lambda c: c.get("above_sma20") is True),
    Condition("종가<SMA20",     lambda c: c.get("above_sma20") is False),
    Condition("SMA20>SMA50",   lambda c: c.get("sma_up") is True),
    Condition("SMA20<SMA50",   lambda c: c.get("sma_up") is False),
    Condition("ADX>25",        lambda c: _get(c, "adx") is not None and c["adx"] > 25),
    Condition("ADX<20",        lambda c: _get(c, "adx") is not None and c["adx"] < 20),
    Condition("RVOL>1.5",      lambda c: _get(c, "rvol") is not None and c["rvol"] > 1.5),
    Condition("RVOL<0.8",      lambda c: _get(c, "rvol") is not None and c["rvol"] < 0.8),
    Condition("ATR%>3",        lambda c: _get(c, "atrp") is not None and c["atrp"] > 3),
    Condition("ATR%<1.5",      lambda c: _get(c, "atrp") is not None and c["atrp"] < 1.5),
    Condition("ROC10>5",       lambda c: _get(c, "roc") is not None and c["roc"] > 5),
    Condition("ROC10<-5",      lambda c: _get(c, "roc") is not None and c["roc"] < -5),
    Condition("52주고점근접",    lambda c: _get(c, "near_high") is not None and c["near_high"] > 0.95),
    Condition("52주저점근접",    lambda c: _get(c, "near_high") is not None and c["near_high"] < 0.6),
]


# ====================================================================== 통계


@dataclass
class PatternStats:
    sample_size: int = 0
    wins: int = 0
    total_return: float = 0.0
    returns: list[float] = field(default_factory=list)
    mae_sum: float = 0.0
    mfe_sum: float = 0.0

    def add(self, ret: float, mae: float, mfe: float) -> None:
        self.sample_size += 1
        self.wins += 1 if ret > 0 else 0
        self.total_return += ret
        self.returns.append(ret)
        self.mae_sum += mae
        self.mfe_sum += mfe

    @property
    def win_rate(self) -> float:
        return self.wins / self.sample_size if self.sample_size else 0.0

    @property
    def avg_return(self) -> float:
        return self.total_return / self.sample_size if self.sample_size else 0.0

    @property
    def median_return(self) -> float:
        if not self.returns:
            return 0.0
        s = sorted(self.returns)
        m = len(s) // 2
        return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2

    @property
    def worst_return(self) -> float:
        return min(self.returns) if self.returns else 0.0

    def to_dict(self) -> dict:
        return {
            "sample_size": self.sample_size,
            "win_rate_pct": round(self.win_rate * 100, 2),
            "avg_return_pct": round(self.avg_return * 100, 3),
            "median_return_pct": round(self.median_return * 100, 3),
            "worst_return_pct": round(self.worst_return * 100, 3),
            "avg_mae_pct": round(self.mae_sum / self.sample_size * 100, 3) if self.sample_size else 0.0,
            "avg_mfe_pct": round(self.mfe_sum / self.sample_size * 100, 3) if self.sample_size else 0.0,
        }


@dataclass
class Pattern:
    pattern_id: str
    conditions: tuple[str, ...]
    horizon: int
    train: PatternStats = field(default_factory=PatternStats)
    validation: PatternStats = field(default_factory=PatternStats)
    test: PatternStats = field(default_factory=PatternStats)
    verdict: str = "UNTESTED"
    direction: str = "NONE"          # UP | DOWN | NONE
    reasons: list[str] = field(default_factory=list)
    market_regime: str = "all"
    sector: str = "all"
    # ★ Phase 20b — 통계적 근거
    significance: dict = field(default_factory=dict)   # OOS 이항검정 결과
    walk_forward: dict = field(default_factory=dict)   # walk-forward 결과
    survived_correction: bool | None = None            # 다중검정 보정 통과 여부
    samples: list = field(default_factory=list, repr=False)   # (idx, ret) — 내부용

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "conditions": list(self.conditions),
            "horizon_days": self.horizon,
            "direction": self.direction,
            "sector": self.sector,
            "market_regime": self.market_regime,
            "train": self.train.to_dict(),
            "validation": self.validation.to_dict(),
            "test_out_of_sample": self.test.to_dict(),
            "verdict": self.verdict,
            "significance": self.significance,
            "walk_forward": self.walk_forward,
            "survived_multiple_testing_correction": self.survived_correction,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class TimeSplit:
    """시간 순 분할. 무작위 분할이 아닙니다."""
    train: tuple[int, int]
    validation: tuple[int, int]
    test: tuple[int, int]

    def overlaps(self) -> bool:
        return not (self.train[1] <= self.validation[0] <= self.validation[1] <= self.test[0])

    def to_dict(self) -> dict:
        return {
            "train": list(self.train),
            "validation": list(self.validation),
            "test_out_of_sample": list(self.test),
            "note": "시간 순으로 자릅니다. 무작위 분할은 미래를 과거에 섞습니다.",
        }


# ====================================================================== 마이너


class PatternMiner:
    def __init__(
        self,
        horizon: int = 5,
        max_conditions: int = 2,
        min_sample_train: int = 40,
        # 홀드아웃 표본이 10건이면 승률 0% 도 우연히 나옵니다.
        # 25건 이상은 되어야 방향 판단에 최소한의 의미가 생깁니다.
        min_sample_holdout: int = 25,
        min_edge: float = 0.02,        # 승률이 52% 는 넘어야 의미
        warmup: int = 60,
        # ★ Phase 20b
        alpha: float = 0.05,           # 유의수준
        correction: str = "bh",        # "bh" | "bonferroni" | "none"
        walk_forward_folds: int = 5,
        min_walk_forward_consistency: float = 0.6,
    ):
        self.horizon = horizon
        self.max_conditions = max_conditions
        self.min_sample_train = min_sample_train
        self.min_sample_holdout = min_sample_holdout
        self.min_edge = min_edge
        self.warmup = warmup
        self.alpha = alpha
        self.correction = correction
        self.walk_forward_folds = walk_forward_folds
        self.min_walk_forward_consistency = min_walk_forward_consistency
        self.last_correction: dict = {}

    # ------------------------------------------------------------------
    @staticmethod
    def make_split(n: int, warmup: int, horizon: int) -> TimeSplit:
        usable_start = warmup
        usable_end = n - horizon - 1
        span = usable_end - usable_start
        if span < 60:
            raise ValueError("패턴 탐색에는 최소 60봉 이상의 사용 가능 구간이 필요합니다")
        a = usable_start + int(span * 0.50)
        b = usable_start + int(span * 0.75)
        return TimeSplit((usable_start, a), (a, b), (b, usable_end))

    # ------------------------------------------------------------------
    def _contexts(self, series: OHLCV) -> list[dict | None]:
        """각 시점의 조건 판정용 지표 묶음. 전부 '그 시점까지'의 값입니다."""
        closes, highs, lows, vols = series.closes, series.highs, series.lows, series.volumes
        n = len(closes)
        r = rsi(closes, 14)
        s20 = sma(closes, 20)
        s50 = sma(closes, 50)
        a14 = adx(highs, lows, closes, 14)
        at = atr(highs, lows, closes, 14)
        rv = relative_volume(vols, 20)
        rc = roc(closes, 10)

        out: list[dict | None] = []
        for i in range(n):
            if i < self.warmup:
                out.append(None)
                continue
            window_hi = max(highs[max(0, i - 251): i + 1])
            ctx = {
                "rsi": r[i],
                "above_sma20": None if s20[i] is None else closes[i] > s20[i],
                "sma_up": None if (s20[i] is None or s50[i] is None) else s20[i] > s50[i],
                "adx": a14[i],
                "rvol": rv[i],
                "atrp": None if at[i] is None or closes[i] == 0 else at[i] / closes[i] * 100,
                "roc": rc[i],
                "near_high": (closes[i] / window_hi) if window_hi else None,
            }
            out.append(ctx)
        return out

    def _outcome(self, series: OHLCV, i: int) -> tuple[float, float, float] | None:
        """i 시점 이후 horizon 봉의 (수익률, MAE, MFE). ★ 채점 전용."""
        j = i + self.horizon
        if j >= len(series):
            return None
        start = series.closes[i]
        if start <= 0:
            return None
        end = series.closes[j]
        window = series[i + 1: j + 1]
        mfe = (max(window.highs) - start) / start
        mae = (min(window.lows) - start) / start
        return (end - start) / start, mae, mfe

    # ------------------------------------------------------------------
    def mine(self, datasets: dict[str, OHLCV], sector: str = "all") -> list[Pattern]:
        """여러 종목 시계열에서 패턴을 찾고, 홀드아웃으로 검증합니다."""
        # 조건 조합 생성 (1개짜리 + 2개짜리)
        combos: list[tuple[str, ...]] = []
        names = [c.name for c in CONDITIONS]
        for k in range(1, self.max_conditions + 1):
            combos.extend(combinations(names, k))
        by_name = {c.name: c for c in CONDITIONS}

        patterns: dict[tuple[str, ...], Pattern] = {
            combo: Pattern(
                pattern_id="P" + "|".join(combo),
                conditions=combo, horizon=self.horizon, sector=sector,
            )
            for combo in combos
        }

        split_info: TimeSplit | None = None

        for symbol, series in datasets.items():
            n = len(series)
            try:
                split = self.make_split(n, self.warmup, self.horizon)
            except ValueError:
                continue
            split_info = split
            if split.overlaps():
                raise RuntimeError("분할 구간이 겹칩니다 — 과적합 방지 규칙 위반")

            ctxs = self._contexts(series)

            for i in range(self.warmup, n - self.horizon - 1):
                ctx = ctxs[i]
                if ctx is None:
                    continue
                out = self._outcome(series, i)
                if out is None:
                    continue
                ret, mae, mfe = out

                if split.train[0] <= i < split.train[1]:
                    bucket = "train"
                elif split.validation[0] <= i < split.validation[1]:
                    bucket = "validation"
                elif split.test[0] <= i < split.test[1]:
                    bucket = "test"
                else:
                    continue

                active = {name for name in names if by_name[name](ctx)}
                for combo, pat in patterns.items():
                    if all(c in active for c in combo):
                        getattr(pat, bucket).add(ret, mae, mfe)
                        # walk-forward 용: 발생 지점과 결과를 그대로 보관
                        pat.samples.append((i, ret))

        results = [self._judge(p) for p in patterns.values()]
        self._mark_redundant(results)

        # ★ Phase 20b — 여기서부터가 새로 붙은 통계 관문입니다.
        if split_info:
            self._attach_walk_forward(results, split_info)
        self._apply_multiple_testing(results)

        results.sort(key=lambda p: (p.verdict != "STRONG", -abs(p.test.win_rate - 0.5)))
        if split_info:
            for p in results:
                p.reasons.append(f"분할: {split_info.to_dict()}")
        for p in results:
            p.samples = []          # 결과 객체를 가볍게 유지합니다
        return results

    # ------------------------------------------------------------------
    def _attach_walk_forward(self, patterns: list[Pattern],
                             split: TimeSplit) -> None:
        """한 번의 분할 운에 기대지 않도록 창을 밀어가며 다시 검증합니다."""
        if self.walk_forward_folds < 2:
            return
        lo = split.train[0]
        hi = split.test[1]
        for p in patterns:
            # 이미 표본 부족·무우위로 떨어진 것은 계산할 필요가 없습니다.
            if p.verdict in ("INSUFFICIENT_SAMPLE", "NO_EDGE", "REDUNDANT"):
                continue
            wf = walk_forward(
                p.samples, lo, hi,
                n_folds=self.walk_forward_folds,
                min_fold_sample=max(10, self.min_sample_holdout // 2),
                min_edge=self.min_edge,
            )
            p.walk_forward = wf.to_dict()

            if p.verdict != "STRONG":
                continue
            if not wf.evaluated:
                p.verdict = "UNVERIFIED"
                p.reasons.insert(0, (
                    "walk-forward 회차를 하나도 평가하지 못했습니다 "
                    "(구간마다 표본 부족). 한 번의 분할 결과만으로는 인정하지 않습니다."
                ))
                continue
            if wf.consistency < self.min_walk_forward_consistency:
                p.verdict = "FAILED_WALK_FORWARD"
                p.reasons.insert(0, (
                    f"walk-forward {len(wf.evaluated)}회 중 {wf.agreements}회만 "
                    f"방향이 맞았습니다 ({wf.consistency:.0%} < "
                    f"{self.min_walk_forward_consistency:.0%}). "
                    "3구간 분할에서 통과한 것은 한 번의 운으로 보입니다."
                ))

    # ------------------------------------------------------------------
    def _apply_multiple_testing(self, patterns: list[Pattern]) -> None:
        """★ 이 프로젝트에서 가장 컸던 통계적 약점을 막는 곳입니다.

        후보를 153개 검정하면 우위가 전혀 없어도 약 8개가 p<0.05 를
        우연히 만족합니다. 보정 없이 'STRONG 8개' 라고 말하면
        그 8개는 아무 의미가 없습니다.
        """
        # 1) 모든 후보의 OOS 유의성 계산 (겹치는 창 보정 포함)
        for p in patterns:
            if p.test.sample_size > 0:
                p.significance = significance_report(
                    wins=p.test.wins, n=p.test.sample_size,
                    horizon=self.horizon, returns=p.test.returns,
                )

        if self.correction == "none":
            return

        # 2) 실제로 '검정한' 후보만 보정 대상입니다.
        #    표본 부족으로 시작도 못 한 후보까지 세면 보정이 과해집니다.
        tested = [p for p in patterns
                  if p.significance and p.verdict not in
                  ("INSUFFICIENT_SAMPLE", "REDUNDANT")]
        if not tested:
            return

        pvals = [p.significance["p_value"] for p in tested]
        mt = correct_multiple_tests(pvals, alpha=self.alpha)
        survivors = set(mt.survivors_bh if self.correction == "bh"
                        else mt.survivors_bonferroni)

        self.last_correction = mt.to_dict()

        for i, p in enumerate(tested):
            p.survived_correction = i in survivors
            p.significance["correction"] = {
                "method": "Benjamini-Hochberg FDR" if self.correction == "bh"
                          else "Bonferroni",
                "n_tests": mt.n_tests,
                "threshold": round(mt.bh_threshold if self.correction == "bh"
                                   else mt.bonferroni_threshold, 6),
                "survived": p.survived_correction,
            }
            if p.verdict == "STRONG" and not p.survived_correction:
                p.verdict = "NOT_SIGNIFICANT"
                p.reasons.insert(0, (
                    f"OOS p-value {p.significance['p_value']:.4f} 가 "
                    f"{mt.n_tests}개 동시 검정 보정 기준을 넘지 못했습니다. "
                    "이 정도 승률은 후보를 이만큼 뒤지면 우연히도 나옵니다."
                ))

    # ------------------------------------------------------------------
    @staticmethod
    def _mark_redundant(patterns: list[Pattern]) -> None:
        """조건을 하나 더 붙였는데 표본이 그대로면, 그 조건은 아무 일도 안 한 것입니다.

        이런 패턴을 따로 세면 "STRONG 패턴 8개 발견"이 부풀려집니다.
        실제로는 같은 패턴을 여러 번 센 것입니다.
        """
        by_conditions = {p.conditions: p for p in patterns}
        for p in patterns:
            if len(p.conditions) < 2 or p.verdict != "STRONG":
                continue
            for i in range(len(p.conditions)):
                subset = tuple(c for j, c in enumerate(p.conditions) if j != i)
                parent = by_conditions.get(subset)
                if parent is None:
                    continue
                same = (
                    parent.train.sample_size == p.train.sample_size
                    and parent.test.sample_size == p.test.sample_size
                )
                if same:
                    p.verdict = "REDUNDANT"
                    p.reasons.insert(
                        0,
                        f"조건 '{p.conditions[i]}' 를 빼도 표본이 같습니다 "
                        f"(= '{' + '.join(subset)}' 와 동일한 패턴). 중복 계상 방지를 위해 제외합니다.",
                    )
                    break

    # ------------------------------------------------------------------
    def _judge(self, p: Pattern) -> Pattern:
        """찾은 패턴을 믿을지 결정합니다. 여기가 이 파일의 핵심입니다."""
        reasons: list[str] = []

        if p.train.sample_size < self.min_sample_train:
            p.verdict = "INSUFFICIENT_SAMPLE"
            reasons.append(
                f"학습 구간 표본 {p.train.sample_size}건 < 최소 {self.min_sample_train}건 — "
                "표본이 적으면 운을 실력으로 착각하게 됩니다"
            )
            p.reasons = reasons
            return p

        train_edge = p.train.win_rate - 0.5
        if abs(train_edge) < self.min_edge:
            p.verdict = "NO_EDGE"
            reasons.append(f"학습 구간 승률 {p.train.win_rate:.1%} — 동전던지기와 구별되지 않음")
            p.reasons = reasons
            return p

        direction = 1 if train_edge > 0 else -1
        p.direction = "UP" if direction > 0 else "DOWN"

        if p.validation.sample_size < self.min_sample_holdout:
            p.verdict = "UNVERIFIED"
            reasons.append(f"검증 구간 표본 부족 ({p.validation.sample_size}건)")
            p.reasons = reasons
            return p

        val_edge = p.validation.win_rate - 0.5
        if (1 if val_edge > 0 else -1) != direction or abs(val_edge) < self.min_edge / 2:
            p.verdict = "FAILED_VALIDATION"
            reasons.append(
                f"학습 승률 {p.train.win_rate:.1%} → 검증 {p.validation.win_rate:.1%}. "
                "학습 구간에만 맞는 패턴(과적합)으로 판단합니다"
            )
            p.reasons = reasons
            return p

        if p.test.sample_size < self.min_sample_holdout:
            p.verdict = "UNVERIFIED"
            reasons.append(f"검증(OOS) 구간 표본 부족 ({p.test.sample_size}건)")
            p.reasons = reasons
            return p

        test_edge = p.test.win_rate - 0.5
        if (1 if test_edge > 0 else -1) != direction:
            p.verdict = "FAILED_OUT_OF_SAMPLE"
            reasons.append(
                f"학습 {p.train.win_rate:.1%} / 검증 {p.validation.win_rate:.1%} 이었으나 "
                f"OOS 에서 {p.test.win_rate:.1%} 로 방향이 뒤집혔습니다"
            )
            p.reasons = reasons
            return p

        if abs(test_edge) < self.min_edge / 2:
            p.verdict = "WEAK"
            reasons.append(f"OOS 승률 {p.test.win_rate:.1%} — 우위가 약합니다")
        else:
            p.verdict = "STRONG"
            reasons.append(
                f"학습 {p.train.win_rate:.1%} / 검증 {p.validation.win_rate:.1%} / "
                f"OOS {p.test.win_rate:.1%} — 세 구간에서 방향이 일치합니다"
            )
        reasons.append(
            "주의: 통계적 경향이며 미래를 보장하지 않습니다. "
            "표본 수와 최악 손실(worst_return)을 반드시 함께 보십시오."
        )
        p.reasons = reasons
        return p

    # ------------------------------------------------------------------
    @staticmethod
    def summary(patterns: Sequence[Pattern], data_source: str = "MOCK_SYNTHETIC",
                horizon: int = 5, correction: dict | None = None) -> dict:
        counts: dict[str, int] = {}
        for p in patterns:
            counts[p.verdict] = counts.get(p.verdict, 0) + 1
        strong = [p for p in patterns if p.verdict == "STRONG"]

        # ★ 정직성 경고 — 이걸 빼면 사용자가 숫자를 오해합니다.
        warnings = [
            f"표본이 겹칩니다: {horizon}일 수익률 창이 서로 중첩되므로 "
            "표본들이 서로 독립이 아닙니다. 승률의 통계적 유의성은 표본 수가 "
            "시사하는 것보다 낮습니다.",
            "여러 종목에 같은 조건을 적용해 합산했습니다. 종목 간 상관이 높으면 "
            "실제 독립 표본 수는 더 적습니다.",
            "STRONG 은 '세 구간에서 방향이 일치했다'는 뜻이지 "
            "'앞으로도 통한다'는 뜻이 아닙니다.",
        ]
        if data_source == "MOCK_SYNTHETIC":
            warnings.insert(0, (
                "⚠ 현재 데이터는 합성(MOCK) 시계열입니다. 생성기에 의도적으로 "
                "완만한 사이클이 들어 있어 모멘텀 조건이 잘 맞습니다. "
                "여기서 나온 높은 승률은 실제 시장의 우위를 전혀 의미하지 않습니다. "
                "실제 시세가 연결되는 Phase 21 이후의 결과만 의미가 있습니다."
            ))

        # ★ Phase 20b — 다중검정 보정 전후를 나란히 보여줍니다.
        would_be_strong = [
            p for p in patterns
            if p.survived_correction is False and p.verdict == "NOT_SIGNIFICANT"
        ]
        if correction:
            warnings.append(
                f"동시 검정 {correction.get('n_tests', 0)}건에 대해 "
                f"{'Benjamini-Hochberg FDR' if correction.get('benjamini_hochberg_threshold') is not None else '보정'} "
                f"를 적용했습니다. 보정이 없었다면 우연만으로도 약 "
                f"{correction.get('expected_false_positives_if_uncorrected', 0):.0f}개가 "
                "'유의' 하게 나왔을 것입니다."
            )
        if would_be_strong:
            warnings.append(
                f"세 구간을 모두 통과했지만 다중검정 보정에서 탈락한 후보가 "
                f"{len(would_be_strong)}개 있습니다. 보정을 하지 않았다면 "
                "이것들이 'STRONG' 으로 보고되었을 것입니다."
            )

        return {
            "data_source": data_source,
            "is_mock": data_source == "MOCK_SYNTHETIC",
            "candidates_tested": len(patterns),
            "by_verdict": counts,
            "strong": [p.to_dict() for p in strong[:20]],
            "multiple_testing_correction": correction or {
                "applied": False,
                "note": "보정을 적용하지 않았습니다 — 결과를 유의하다고 해석하지 마십시오.",
            },
            "rejected_by_correction": len(would_be_strong),
            "warnings": warnings,
            "note": (
                "후보를 많이 찾는 것이 목표가 아닙니다. "
                "학습·검증·OOS 세 구간을 모두 통과한 것만 STRONG 으로 인정합니다. "
                "대부분의 후보가 기각되는 것이 정상입니다."
            ),
        }
