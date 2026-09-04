"""Effective Learning Time — '진짜' 공부한 시간만 셉니다.

프로젝트 원칙 §28
    다음은 학습시간에서 제외한다:
      idle / 중복 읽기 / 스팸 / 유효하지 않은 데이터 /
      에러 루프 / 대기 / 동일 문서 재독

즉 화면만 켜두면 시간이 쌓이는 방식이 아닙니다.
4시간 목표는 '유효 학습' 기준입니다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

DAILY_TARGET_SECONDS = 4 * 60 * 60  # 4시간

# 유효 학습으로 인정하는 활동
PRODUCTIVE = {
    "chart_exercise",       # 차트 문제 풀이
    "prediction_review",    # 과거 예측 복기
    "document_study",       # 새 자료 정독
    "knowledge_verify",     # 지식 검증
    "contradiction_search", # 반대 근거 탐색
    "exam",                 # 시험
    "failure_analysis",     # 오답 분석
}

# 시간에서 빼는 활동
NON_PRODUCTIVE = {
    "idle",
    "waiting",
    "duplicate_read",
    "spam_filtered",
    "invalid_data",
    "error_retry",
    "blocked",
}


@dataclass
class LearningActivity:
    activity: str
    seconds: float
    detail: str = ""
    ts: float = field(default_factory=time.time)

    @property
    def productive(self) -> bool:
        return self.activity in PRODUCTIVE


@dataclass
class EffectiveTimeTracker:
    """에이전트 한 명의 하루 학습 시간 장부."""

    agent_id: str
    target_seconds: int = DAILY_TARGET_SECONDS
    effective_seconds: float = 0.0
    wasted_seconds: float = 0.0
    by_activity: dict[str, float] = field(default_factory=dict)
    wasted_by_reason: dict[str, float] = field(default_factory=dict)
    log: list[LearningActivity] = field(default_factory=list)
    max_log: int = 200

    # 중복 읽기 방지 — 같은 문서를 또 읽으면 시간으로 안 쳐줍니다
    _seen_hashes: set[str] = field(default_factory=set)

    def record(self, activity: str, seconds: float, detail: str = "",
               content_hash: str | None = None) -> bool:
        """활동을 기록합니다. 유효 학습으로 인정되면 True."""
        act = LearningActivity(activity=activity, seconds=seconds, detail=detail)

        # 중복 문서 검사
        if content_hash is not None:
            if content_hash in self._seen_hashes:
                act = LearningActivity("duplicate_read", seconds, f"중복: {detail}")
            else:
                self._seen_hashes.add(content_hash)

        self.log.append(act)
        if len(self.log) > self.max_log:
            self.log.pop(0)

        if act.productive:
            self.effective_seconds += act.seconds
            self.by_activity[act.activity] = self.by_activity.get(act.activity, 0.0) + act.seconds
            return True

        self.wasted_seconds += act.seconds
        self.wasted_by_reason[act.activity] = (
            self.wasted_by_reason.get(act.activity, 0.0) + act.seconds
        )
        return False

    @property
    def progress(self) -> float:
        return min(1.0, self.effective_seconds / self.target_seconds) if self.target_seconds else 0.0

    @property
    def efficiency(self) -> float:
        """전체 시간 중 유효 학습 비율. 낮으면 시스템이 헛돌고 있다는 뜻."""
        total = self.effective_seconds + self.wasted_seconds
        return self.effective_seconds / total if total else 0.0

    def reset_day(self) -> None:
        self.effective_seconds = 0.0
        self.wasted_seconds = 0.0
        self.by_activity.clear()
        self.wasted_by_reason.clear()
        self._seen_hashes.clear()

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "target_minutes": round(self.target_seconds / 60),
            "effective_minutes": round(self.effective_seconds / 60, 1),
            "wasted_minutes": round(self.wasted_seconds / 60, 1),
            "progress_pct": round(self.progress * 100, 1),
            "efficiency_pct": round(self.efficiency * 100, 1),
            "by_activity_minutes": {k: round(v / 60, 1) for k, v in self.by_activity.items()},
            "excluded_minutes": {k: round(v / 60, 1) for k, v in self.wasted_by_reason.items()},
            "note": "idle·중복·스팸·에러는 학습시간에서 제외됩니다",
        }
