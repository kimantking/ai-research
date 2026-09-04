"""수집기(Collector) 공통 인터페이스.

★ 설계 원칙
   외부 수집 도구는 언제든 바뀌거나 사라집니다.
   그래서 우리 코드는 '도구'가 아니라 '인터페이스'에 의존합니다.

   그리고 더 중요한 것:
   **수집기는 수집만 합니다. 판정은 우리가 합니다.**
   어떤 도구가 무엇을 가져오든, 그것은 Research Firewall 을 통과해야
   에이전트에게 도달합니다. 외부 도구를 신뢰하지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable


class CollectorStatus(str, Enum):
    CONNECTED = "CONNECTED"          # 사용 가능
    NOT_INSTALLED = "NOT_INSTALLED"  # 도구가 설치되어 있지 않음 (오류 아님)
    NEEDS_AUTH = "NEEDS_AUTH"        # 설치는 됐으나 자격증명 필요
    ERROR = "ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    DISABLED = "DISABLED"            # 설정에서 꺼둠


@dataclass
class SourceDocument:
    """수집된 원문 한 건.

    ★ tier 를 여기서 정하지 않습니다.
      수집기는 '어디서 가져왔는지'만 말하고,
      등급 판정은 packages/source_validation/tiers.py 가 합니다.
    """

    url: str
    title: str = ""
    body: str = ""
    domain: str = ""
    channel: str = ""                     # web / twitter / reddit / youtube ...
    published: datetime | None = None
    author: str = ""
    collector: str = ""                   # 어느 수집기가 가져왔는가
    raw_ref: str = ""                     # 원본 저장 위치 (RAW STORAGE)
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # ★ 수집 단계에서는 항상 미검증입니다.
    #   Research Firewall 을 통과해야 이 값이 바뀝니다.
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "domain": self.domain,
            "channel": self.channel,
            "author": self.author,
            "published": self.published.isoformat() if self.published else None,
            "collector": self.collector,
            "fetched_at": self.fetched_at.isoformat(),
            "body_chars": len(self.body),
            "verified": self.verified,
        }


@dataclass
class CollectorHealth:
    collector_id: str
    name: str
    status: CollectorStatus
    detail: str = ""
    version: str = ""
    channels_available: list[str] = field(default_factory=list)
    channels_need_auth: list[str] = field(default_factory=list)
    install_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.collector_id,
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "version": self.version,
            "channels_available": self.channels_available,
            "channels_need_auth": self.channels_need_auth,
            "install_hint": self.install_hint,
        }


@runtime_checkable
class Collector(Protocol):
    """수집기 인터페이스."""

    collector_id: str

    def health(self) -> CollectorHealth:
        """설치·인증 상태. 설치되지 않은 것은 오류가 아닙니다."""
        ...

    def read(self, url: str, timeout: float = 30.0) -> SourceDocument | None:
        """URL 한 건을 읽어옵니다."""
        ...

    def search(self, query: str, channel: str = "web",
               limit: int = 10, timeout: float = 60.0) -> list[SourceDocument]:
        """검색합니다."""
        ...
