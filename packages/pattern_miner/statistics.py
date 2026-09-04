"""패턴 검정에 쓰는 통계 도구 (표준 라이브러리만).

★ 이 파일이 생긴 이유

    이전까지 Pattern Miner 의 가장 큰 약점은 이것이었습니다.

        "후보 153개를 검정하면, 아무 우위가 없어도 5%(약 8개)는
         우연히 유의하게 나온다."

    STRONG 8개가 나왔는데 우연으로도 8개가 나온다면, 그 8개는
    아무것도 말해주지 않습니다. 이 파일은 그 문제를 정면으로 다룹니다.

★ 다루는 것

    1. 이항검정 p-value      — 승률이 동전던지기와 다른가
    2. 유효 표본 수(n_eff)   — 5일 수익률 창이 겹치면 표본은 독립이 아닙니다
    3. Bonferroni           — 가장 보수적인 보정
    4. Benjamini-Hochberg   — FDR(거짓발견율) 통제. 실무 표준
    5. 블록 부트스트랩       — 자기상관을 견디는 신뢰구간
    6. 최소 검정력 표본 수    — "이 표본으로 이 우위를 잡을 수 있나"

★ 정직성

    보정을 통과했다고 "진짜 우위"인 것은 아닙니다.
    보정을 통과하지 못하면 "우연과 구별되지 않는다"가 확실해질 뿐입니다.
    이 도구는 **기각을 잘 하기 위한** 도구입니다.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------- 이항검정
def binomial_tail_p(k: int, n: int, p0: float = 0.5) -> float:
    """양측 이항검정 p-value (정확 계산).

    k: 성공 횟수, n: 시행 횟수, p0: 귀무가설 확률.

    "승률 60%, 표본 30건" 이 얼마나 흔한 일인지 알려줍니다.
    답: 아주 흔합니다 (p ≈ 0.36). 그래서 표본 30건은 부족합니다.
    """
    if n <= 0:
        return 1.0
    k = max(0, min(k, n))

    def pmf(i: int) -> float:
        return math.comb(n, i) * (p0 ** i) * ((1 - p0) ** (n - i))

    observed = pmf(k)
    # 관측된 것만큼 또는 그보다 더 '극단적인' 결과의 확률을 모두 더합니다.
    # (부동소수 오차로 같은 값이 빠지지 않도록 아주 작은 여유를 둡니다)
    total = sum(pmf(i) for i in range(n + 1) if pmf(i) <= observed * (1 + 1e-9))
    return min(1.0, total)


def effective_sample_size(n: int, horizon: int, overlap: bool = True) -> int:
    """겹치는 수익률 창을 고려한 유효 표본 수.

    5일 수익률을 매일 계산하면, 연속한 표본은 4일치를 공유합니다.
    사실상 독립인 관측은 n/5 개에 가깝습니다.

    이 보정을 하지 않으면 p-value 가 **실제보다 훨씬 작게** 나옵니다.
    즉 없는 우위를 있다고 말하게 됩니다.
    """
    if not overlap or horizon <= 1:
        return max(0, n)
    return max(0, int(n / horizon))


# ---------------------------------------------------------------- 다중검정
@dataclass
class MultipleTestResult:
    n_tests: int
    alpha: float
    bonferroni_threshold: float
    bh_threshold: float
    survivors_bonferroni: list[int] = field(default_factory=list)
    survivors_bh: list[int] = field(default_factory=list)
    expected_false_positives_uncorrected: float = 0.0

    def to_dict(self) -> dict:
        return {
            "n_tests": self.n_tests,
            "alpha": self.alpha,
            "bonferroni_threshold": self.bonferroni_threshold,
            "benjamini_hochberg_threshold": round(self.bh_threshold, 6),
            "survived_bonferroni": len(self.survivors_bonferroni),
            "survived_bh_fdr": len(self.survivors_bh),
            "expected_false_positives_if_uncorrected":
                round(self.expected_false_positives_uncorrected, 1),
            "note": (
                f"{self.n_tests}개를 검정하면 우위가 전혀 없어도 "
                f"약 {self.expected_false_positives_uncorrected:.0f}개가 "
                f"p<{self.alpha} 를 우연히 만족합니다. "
                "그래서 보정 없이 '유의하다'고 말할 수 없습니다."
            ),
        }


def correct_multiple_tests(pvalues: Sequence[float],
                           alpha: float = 0.05) -> MultipleTestResult:
    """Bonferroni 와 Benjamini-Hochberg(FDR) 를 함께 계산합니다.

    Bonferroni: alpha/m 보다 작아야 통과. 가장 엄격 — 거의 다 떨어집니다.
    BH-FDR:     p(i) <= (i/m)*alpha 를 만족하는 가장 큰 i 까지 통과.
                "발견한 것 중 거짓이 alpha 비율 이하" 를 보장합니다.
    """
    m = len(pvalues)
    if m == 0:
        return MultipleTestResult(0, alpha, alpha, alpha)

    bonf_thr = alpha / m
    survivors_bonf = [i for i, p in enumerate(pvalues) if p <= bonf_thr]

    order = sorted(range(m), key=lambda i: pvalues[i])
    bh_cutoff_rank = 0
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= (rank / m) * alpha:
            bh_cutoff_rank = rank
    survivors_bh = [order[r - 1] for r in range(1, bh_cutoff_rank + 1)]
    bh_thr = (bh_cutoff_rank / m) * alpha if bh_cutoff_rank else 0.0

    return MultipleTestResult(
        n_tests=m,
        alpha=alpha,
        bonferroni_threshold=bonf_thr,
        bh_threshold=bh_thr,
        survivors_bonferroni=survivors_bonf,
        survivors_bh=sorted(survivors_bh),
        expected_false_positives_uncorrected=m * alpha,
    )


# ---------------------------------------------------------------- 부트스트랩
def block_bootstrap_ci(returns: Sequence[float],
                       block: int = 5,
                       iterations: int = 400,
                       confidence: float = 0.95,
                       seed: int = 20260903) -> dict:
    """평균 수익률의 신뢰구간 (이동 블록 부트스트랩).

    일반 부트스트랩은 표본이 독립이라고 가정합니다.
    수익률은 그렇지 않습니다(자기상관). 그래서 연속한 `block` 개를
    통째로 뽑아 시간 구조를 어느 정도 보존합니다.

    구간이 0을 포함하면 → "평균 수익이 0과 구별되지 않는다".
    """
    n = len(returns)
    if n < block * 3:
        return {"available": False,
                "reason": f"표본 {n}건 — 블록 부트스트랩에는 최소 {block * 3}건 필요"}

    rng = random.Random(seed)
    n_blocks = max(1, n // block)
    means: list[float] = []
    for _ in range(iterations):
        acc = 0.0
        cnt = 0
        for _ in range(n_blocks):
            start = rng.randrange(0, n - block + 1)
            for v in returns[start:start + block]:
                acc += v
                cnt += 1
        means.append(acc / cnt if cnt else 0.0)

    means.sort()
    lo_i = int((1 - confidence) / 2 * len(means))
    hi_i = int((1 + confidence) / 2 * len(means)) - 1
    lo, hi = means[lo_i], means[max(lo_i, hi_i)]
    return {
        "available": True,
        "mean_pct": round(sum(returns) / n * 100, 4),
        "ci_low_pct": round(lo * 100, 4),
        "ci_high_pct": round(hi * 100, 4),
        "confidence": confidence,
        "block_size": block,
        "iterations": iterations,
        "excludes_zero": (lo > 0) or (hi < 0),
        "note": (
            "신뢰구간이 0을 포함하면 평균 수익이 0과 구별되지 않는다는 뜻입니다."
        ),
    }


# ---------------------------------------------------------------- 검정력
def required_sample_for_edge(edge: float, alpha: float = 0.05,
                             power: float = 0.80) -> int:
    """이 정도 우위를 잡으려면 표본이 몇 개나 필요한가.

    edge: 0.5 대비 승률 차이 (예: 0.05 → 승률 55%)

    "승률 55% 를 80% 검정력으로 잡으려면 약 780건이 필요합니다."
    이 숫자를 보면, 표본 30건짜리 패턴이 왜 무의미한지 바로 이해됩니다.
    """
    if edge <= 0:
        return 10 ** 9
    z_a = 1.959964 if abs(alpha - 0.05) < 1e-9 else 2.575829
    z_b = 0.841621 if abs(power - 0.80) < 1e-9 else 1.281552
    p = 0.5 + edge
    var = p * (1 - p)
    return int(math.ceil(((z_a * 0.5 + z_b * math.sqrt(var)) / edge) ** 2))


def significance_report(wins: int, n: int, horizon: int,
                        returns: Sequence[float] | None = None) -> dict:
    """한 패턴에 대한 통계 보고서 한 장."""
    n_eff = effective_sample_size(n, horizon)
    wins_eff = int(round(wins * (n_eff / n))) if n else 0
    p_raw = binomial_tail_p(wins, n)
    p_eff = binomial_tail_p(wins_eff, n_eff)
    win_rate = wins / n if n else 0.0
    edge = abs(win_rate - 0.5)

    out = {
        "sample_size": n,
        "effective_sample_size": n_eff,
        "win_rate_pct": round(win_rate * 100, 2),
        "p_value_naive": round(p_raw, 6),
        "p_value_overlap_adjusted": round(p_eff, 6),
        "p_value": round(p_eff, 6),          # ★ 실제로 쓰는 값
        "required_sample_for_this_edge": required_sample_for_edge(edge) if edge > 0 else None,
        "note": (
            f"{horizon}일 수익률 창이 겹치므로 표본 {n}건의 실질 정보량은 "
            f"약 {n_eff}건입니다. p-value 는 그 기준으로 계산했습니다."
        ),
    }
    if returns:
        out["bootstrap"] = block_bootstrap_ci(list(returns), block=max(2, horizon))
    return out
