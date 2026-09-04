"""에이전트의 차트 예측 모델 — 온라인 로지스틱 회귀.

왜 이걸로 시작하는가
  - LLM API 키가 없어도 '진짜 학습'이 돌아가야 하기 때문입니다.
  - 가중치가 실제 오답에 따라 갱신되고, 정확도가 실제로 변합니다.
  - 결정론적이라 테스트/재현이 가능합니다.
  - Phase 10 이후 LLM 이 붙으면, 이 모델은 사라지지 않고
    '숫자 근거를 제공하는 도구'로 남습니다. (LLM 이 산수를 틀리는 걸 막음)

각 에이전트는 자기 가중치를 가지며, 서로 다른 경험을 하면
서로 다른 관점을 갖게 됩니다 (Bull/Bear 가 실제로 달라짐).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .features import FEATURE_NAMES


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 60.0)))
    e = math.exp(max(z, -60.0))
    return e / (1.0 + e)


@dataclass
class OnlineChartModel:
    """한 에이전트의 차트 판단 모델."""

    agent_id: str
    weights: list[float] = field(default_factory=lambda: [0.0] * len(FEATURE_NAMES))
    learning_rate: float = 0.06
    l2: float = 0.0005

    # 학습 통계
    samples_seen: int = 0
    correct: int = 0
    # 최근 성적 (rolling)
    recent: list[int] = field(default_factory=list)
    recent_window: int = 50

    # 캘리브레이션: 확신도 구간별 실제 적중률
    calib_bins: list[list[int]] = field(default_factory=lambda: [[0, 0] for _ in range(5)])

    # 성향(bias). Bull 은 상승 쪽에, Bear 는 하락 쪽에 약간 기울어 시작합니다.
    # 이건 '편향'이 아니라 역할 분담이며, 틀리면 데이터가 교정합니다.
    role_prior: float = 0.0

    # ---------------------------------------------------------------- 예측
    def predict_proba(self, x: list[float]) -> float:
        z = sum(w * xi for w, xi in zip(self.weights, x)) + self.role_prior
        return _sigmoid(z)

    def predict(self, x: list[float]) -> tuple[str, float]:
        """(방향, 확신도 0~1)."""
        p = self.predict_proba(x)
        direction = "UP" if p >= 0.5 else "DOWN"
        confidence = abs(p - 0.5) * 2.0
        return direction, confidence

    # ---------------------------------------------------------------- 학습
    def update(self, x: list[float], label: int) -> dict:
        """label: 1=상승, 0=하락. 실제 결과를 보고 가중치를 고칩니다."""
        p = self.predict_proba(x)
        pred_up = p >= 0.5
        was_correct = int(pred_up == bool(label))

        error = label - p
        for i in range(len(self.weights)):
            grad = error * x[i] - self.l2 * self.weights[i]
            self.weights[i] += self.learning_rate * grad

        self.samples_seen += 1
        self.correct += was_correct
        self.recent.append(was_correct)
        if len(self.recent) > self.recent_window:
            self.recent.pop(0)

        # 캘리브레이션 기록
        conf = abs(p - 0.5) * 2.0
        b = min(4, int(conf * 5))
        self.calib_bins[b][0] += 1
        self.calib_bins[b][1] += was_correct

        return {"probability": round(p, 4), "correct": bool(was_correct), "error": round(error, 4)}

    # ---------------------------------------------------------------- 지표
    @property
    def accuracy(self) -> float:
        return self.correct / self.samples_seen if self.samples_seen else 0.0

    @property
    def recent_accuracy(self) -> float:
        return sum(self.recent) / len(self.recent) if self.recent else 0.0

    @property
    def calibration_error(self) -> float:
        """확신도와 실제 적중률의 괴리 (0에 가까울수록 좋음).

        '80% 확신'이라고 말했으면 실제로 80% 맞아야 정직한 것입니다.
        """
        total = sum(b[0] for b in self.calib_bins)
        if total == 0:
            return 0.0
        err = 0.0
        for i, (n, hit) in enumerate(self.calib_bins):
            if n == 0:
                continue
            expected = 0.5 + (i + 0.5) / 5.0 * 0.5   # 구간 중앙의 기대 적중률
            actual = hit / n
            err += (n / total) * abs(expected - actual)
        return err

    def chart_skill_score(self) -> float:
        """차트 스킬 점수 0~100.

        정확도만 보지 않습니다. 캘리브레이션(정직함)과 표본 수도 반영합니다.
        표본이 적으면 점수를 높게 주지 않습니다 — 운을 실력으로 착각하지 않기 위해서.
        """
        if self.samples_seen < 10:
            return round(30.0 + self.samples_seen, 1)
        acc = self.recent_accuracy if self.recent else self.accuracy
        base = (acc - 0.5) * 200.0            # 50% = 0점, 100% = 100점
        base = max(0.0, min(100.0, 50.0 + base * 0.5))
        calib_penalty = self.calibration_error * 40.0
        # 표본 신뢰도: 200개 정도 봐야 온전히 인정
        maturity = min(1.0, self.samples_seen / 200.0)
        score = (base - calib_penalty) * (0.6 + 0.4 * maturity)
        return round(max(0.0, min(100.0, score)), 1)

    # ---------------------------------------------------------------- 직렬화
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "samples_seen": self.samples_seen,
            "accuracy": round(self.accuracy, 4),
            "recent_accuracy": round(self.recent_accuracy, 4),
            "calibration_error": round(self.calibration_error, 4),
            "chart_skill_score": self.chart_skill_score(),
            "weights": {n: round(w, 4) for n, w in zip(FEATURE_NAMES, self.weights)},
        }
