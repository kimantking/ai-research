"""데이터 수집기 — 외부 도구를 우리 인터페이스 뒤에 둡니다.

★ 원칙: 수집기는 수집만 합니다. 판정은 CollectionPipeline 이 합니다.
"""

from .agent_reach import AgentReachCollector
from .base import Collector, CollectorHealth, CollectorStatus, SourceDocument
from .pipeline import (
    AcceptedDocument,
    CollectionPipeline,
    CollectionResult,
    RejectedDocument,
)

__all__ = [
    "Collector", "CollectorHealth", "CollectorStatus", "SourceDocument",
    "AgentReachCollector",
    "CollectionPipeline", "CollectionResult",
    "AcceptedDocument", "RejectedDocument",
]
