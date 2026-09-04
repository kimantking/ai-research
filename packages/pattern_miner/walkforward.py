"""Walk-forward 검증.

★ 3구간 분할만으로는 부족한 이유

    데이터를 학습 50% / 검증 25% / OOS 25% 로 한 번 자르면,
    **그 한 번의 자르기 운**에 결과가 좌우됩니다.
    OOS 구간이 마침 상승장이었다면 매수 패턴은 다 통과합니다.

    Walk-forward 는 창을 앞으로 밀면서 여러 번 반복합니다.

        [학습      ][검증]
             [학습      ][검증]
                  [학습      ][검증]
                       ...

    각 회차마다 "학습 구간에서 정한 방향이 바로 다음 검증 구간에서도
    맞았는가" 를 봅니다. **N회 중 몇 회 맞았는가** 가 결과입니다.

★ 무엇을 막는가

    한 번의 운을 실력으로 오해하는 것.
    "OOS 에서 통했다" 는 1회 관측입니다. Walk-forward 는 그것을 N회로 만듭니다.

★ 여전히 못 막는 것 (정직하게)

    - 창이 겹치므로 회차끼리 완전히 독립이 아닙니다.
    - 전체 기간이 하나의 시장 국면이면 모든 회차가 같은 편향을 겪습니다.
    - **과거에 통했다는 사실은 미래를 보장하지 않습니다.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass
class Fold:
    index: int
    train: tuple[int, int]
    test: tuple[int, int]
    train_n: int = 0
    train_wins: int = 0
    test_n: int = 0
    test_wins: int = 0
    direction: str = "NONE"
    agreed: bool | None = None      # 학습 방향이 검증에서도 맞았는가
    skipped_reason: str = ""

    @property
    def train_win_rate(self) -> float:
        return self.train_wins / self.train_n if self.train_n else 0.0

    @property
    def test_win_rate(self) -> float:
        return self.test_wins / self.test_n if self.test_n else 0.0

    def to_dict(self) -> dict:
        return {
            "fold": self.index,
            "train_range": list(self.train),
            "test_range": list(self.test),
            "train_n": self.train_n,
            "train_win_rate_pct": round(self.train_win_rate * 100, 2),
            "test_n": self.test_n,
            "test_win_rate_pct": round(self.test_win_rate * 100, 2),
            "direction": self.direction,
            "agreed": self.agreed,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class WalkForwardResult:
    folds: list[Fold] = field(default_factory=list)
    min_fold_sample: int = 20

    @property
    def evaluated(self) -> list[Fold]:
        return [f for f in self.folds if f.agreed is not None]

    @property
    def agreements(self) -> int:
        return sum(1 for f in self.evaluated if f.agreed)

    @property
    def consistency(self) -> float:
        ev = self.evaluated
        return self.agreements / len(ev) if ev else 0.0

    def p_value(self) -> float:
        """'방향이 우연히 맞을 확률 50%' 를 귀무가설로 한 이항검정."""
        from .statistics import binomial_tail_p
        ev = self.evaluated
        if not ev:
            return 1.0
        return binomial_tail_p(self.agreements, len(ev))

    def to_dict(self) -> dict:
        ev = self.evaluated
        return {
            "folds_total": len(self.folds),
            "folds_evaluated": len(ev),
            "folds_skipped": len(self.folds) - len(ev),
            "agreements": self.agreements,
            "consistency_pct": round(self.consistency * 100, 2),
            "p_value": round(self.p_value(), 6),
            "min_fold_sample": self.min_fold_sample,
            "detail": [f.to_dict() for f in self.folds],
            "note": (
                "각 회차는 '그 시점까지의 학습 구간에서 정한 방향' 이 "
                "'바로 다음 검증 구간' 에서도 맞았는지만 봅니다. "
                "창이 겹치므로 회차끼리 완전히 독립은 아닙니다."
            ),
        }


def make_folds(start: int, end: int, n_folds: int = 5,
               test_fraction: float = 0.25,
               anchored: bool = True) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """[start, end) 를 walk-forward 구간으로 나눕니다.

    anchored=True  : 학습 구간이 계속 늘어납니다 (확장창). 기본값.
    anchored=False : 학습 구간 길이가 고정입니다 (이동창).
    """
    span = end - start
    if n_folds < 2 or span < n_folds * 8:
        return []

    step = span // (n_folds + 1)
    if step <= 0:
        return []

    folds: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for k in range(1, n_folds + 1):
        train_end = start + step * k
        test_end = min(end, train_end + step)
        if test_end <= train_end:
            break
        train_start = start if anchored else max(start, train_end - step * 2)
        folds.append(((train_start, train_end), (train_end, test_end)))
    return folds


def walk_forward(
    samples: Sequence[tuple[int, float]],
    start: int,
    end: int,
    n_folds: int = 5,
    min_fold_sample: int = 20,
    min_edge: float = 0.02,
    anchored: bool = True,
) -> WalkForwardResult:
    """패턴이 발생한 지점들을 walk-forward 로 검증합니다.

    samples: (봉 인덱스, 수익률) 목록 — 그 패턴의 조건이 만족된 시점들
    """
    result = WalkForwardResult(min_fold_sample=min_fold_sample)
    fold_ranges = make_folds(start, end, n_folds, anchored=anchored)

    for i, (tr, te) in enumerate(fold_ranges, start=1):
        fold = Fold(index=i, train=tr, test=te)

        tr_hits = [r for (idx, r) in samples if tr[0] <= idx < tr[1]]
        te_hits = [r for (idx, r) in samples if te[0] <= idx < te[1]]
        fold.train_n = len(tr_hits)
        fold.train_wins = sum(1 for r in tr_hits if r > 0)
        fold.test_n = len(te_hits)
        fold.test_wins = sum(1 for r in te_hits if r > 0)

        if fold.train_n < min_fold_sample:
            fold.skipped_reason = f"학습 표본 {fold.train_n}건 < {min_fold_sample}건"
            result.folds.append(fold)
            continue
        if fold.test_n < min_fold_sample:
            fold.skipped_reason = f"검증 표본 {fold.test_n}건 < {min_fold_sample}건"
            result.folds.append(fold)
            continue

        edge = fold.train_win_rate - 0.5
        if abs(edge) < min_edge:
            fold.skipped_reason = f"학습 우위 {edge:+.1%} — 방향을 정할 수 없음"
            result.folds.append(fold)
            continue

        fold.direction = "UP" if edge > 0 else "DOWN"
        test_edge = fold.test_win_rate - 0.5
        fold.agreed = (test_edge > 0) if edge > 0 else (test_edge < 0)
        result.folds.append(fold)

    return result
