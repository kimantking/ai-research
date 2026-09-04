"""학습 엔진 — 에이전트가 실제로 공부하고, 점수가 실제로 움직입니다.

핵심 원칙
  1) 가짜 진행바가 아닙니다. 점수는 실제 측정된 정확도에서 나옵니다.
  2) 미래를 보지 않습니다. 문제를 만들 때 T 시점 이후 캔들은
     애초에 함수에 전달되지 않습니다 (구조적 차단).
  3) 시험은 학습에 쓰지 않은 구간(out-of-sample)에서만 출제합니다.
"""

from .effective_time import EffectiveTimeTracker, LearningActivity
from .exam import ChartExam, ExamResult, SourceExam
from .exercise import ChartExercise, build_exercise, evaluate_exercise
from .features import FEATURE_NAMES, extract_features
from .knowledge import KnowledgeCandidate, KnowledgeStore, VerificationOutcome
from .model import OnlineChartModel

__all__ = [
    "EffectiveTimeTracker", "LearningActivity",
    "ChartExam", "SourceExam", "ExamResult",
    "ChartExercise", "build_exercise", "evaluate_exercise",
    "FEATURE_NAMES", "extract_features",
    "OnlineChartModel",
    "KnowledgeCandidate", "KnowledgeStore", "VerificationOutcome",
]
