"""수집 → 방화벽 → 등급판정 파이프라인.

★ 이 파일이 존재하는 이유

  외부 수집 도구(Agent Reach 등)를 붙이면 편해집니다.
  그런데 편해지는 만큼 위험해집니다 — 도구가 가져온 걸 그대로 믿으면
  스팸·복사기사·루머가 곧장 에이전트 머릿속으로 들어갑니다.

  그래서 **수집기와 에이전트 사이에 반드시 이 파이프라인이 있습니다.**

      Collector  →  Research Firewall  →  Tier 판정  →  Agent
                    (스팸/중복/루머)      (우리 규칙)

  Agent Reach 가 레딧에서 가져왔든 SEC 에서 가져왔든,
  등급은 **우리 규칙**(config/source_tiers/default.yaml)이 정합니다.
  수집기의 말은 참고하지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from packages.source_validation.firewall import FirewallVerdict, ResearchFirewall
from packages.source_validation.lineage import SourceRecord
from packages.source_validation.tiers import SourceTier, rule_of, tier_of_domain

from .base import Collector, CollectorStatus, SourceDocument


@dataclass
class AcceptedDocument:
    """방화벽을 통과한 문서."""

    document: SourceDocument
    tier: SourceTier
    confidence: float
    can_confirm_fact: bool
    penalties: list[str] = field(default_factory=list)
    content_hash: str = ""

    def as_source_record(self, source_id: str) -> SourceRecord:
        return SourceRecord(
            source_id=source_id,
            url=self.document.url,
            domain=self.document.domain,
            tier=self.tier,
            title=self.document.title,
            published=(self.document.published.isoformat()
                       if self.document.published else None),
            confidence=self.confidence,
        )

    def to_dict(self) -> dict:
        return {
            **self.document.to_dict(),
            "tier": self.tier.value,
            "confidence": round(self.confidence, 3),
            "can_confirm_fact": self.can_confirm_fact,
            "penalties": self.penalties,
        }


@dataclass
class RejectedDocument:
    url: str
    domain: str
    reasons: list[str]
    duplicate_of: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url, "domain": self.domain,
            "reasons": self.reasons, "duplicate_of": self.duplicate_of,
        }


@dataclass
class CollectionResult:
    query: str
    channel: str
    collector: str
    collected: int = 0
    accepted: list[AcceptedDocument] = field(default_factory=list)
    rejected: list[RejectedDocument] = field(default_factory=list)
    collector_status: str = ""
    note: str = ""

    @property
    def page_count(self) -> int:
        """읽은 페이지 수. ★ 신뢰도 계산에 쓰면 안 되는 숫자입니다."""
        return len(self.accepted)

    @property
    def independent_evidence_count(self) -> int:
        """서로 다른 도메인 수 — 독립 근거의 하한 추정."""
        return len({a.document.domain for a in self.accepted if a.document.domain})

    @property
    def confirmable_count(self) -> int:
        return len({a.document.domain for a in self.accepted if a.can_confirm_fact})

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "channel": self.channel,
            "collector": self.collector,
            "collector_status": self.collector_status,
            "collected": self.collected,
            "accepted": [a.to_dict() for a in self.accepted],
            "rejected": [r.to_dict() for r in self.rejected],
            "page_count": self.page_count,
            "independent_evidence_count": self.independent_evidence_count,
            "confirmable_source_count": self.confirmable_count,
            "note": self.note or (
                "page_count 는 신뢰도 계산에 사용하지 않습니다. "
                "복사 기사 50건은 독립 근거 1건입니다."
            ),
            "ts": datetime.now(timezone.utc).isoformat(),
        }


class CollectionPipeline:
    """수집기를 감싸서, 결과를 반드시 방화벽에 통과시킵니다."""

    def __init__(self, collector: Collector, config_dir: Path | None = None,
                 firewall: ResearchFirewall | None = None):
        self.collector = collector
        self.config_dir = config_dir
        self.firewall = firewall or ResearchFirewall(config_dir=config_dir)
        self._seq = 0

    # ------------------------------------------------------------------
    def collect(self, query: str, channel: str = "web",
                limit: int = 10) -> CollectionResult:
        health = self.collector.health()
        result = CollectionResult(
            query=query, channel=channel,
            collector=getattr(self.collector, "collector_id", "unknown"),
            collector_status=health.status.value,
        )

        if health.status is not CollectorStatus.CONNECTED:
            result.note = (
                f"수집기를 쓸 수 없습니다 ({health.status.value}). "
                f"{health.detail} "
                "시스템은 이 수집기 없이도 정상 동작합니다."
            )
            return result

        docs = self.collector.search(query, channel=channel, limit=limit)
        result.collected = len(docs)
        for doc in docs:
            self._screen(doc, result)
        return result

    def read_url(self, url: str) -> CollectionResult:
        health = self.collector.health()
        result = CollectionResult(
            query=url, channel="web",
            collector=getattr(self.collector, "collector_id", "unknown"),
            collector_status=health.status.value,
        )
        if health.status is not CollectorStatus.CONNECTED:
            result.note = f"수집기를 쓸 수 없습니다 ({health.status.value})."
            return result

        doc = self.collector.read(url)
        if doc is None:
            result.note = "문서를 가져오지 못했습니다."
            return result
        result.collected = 1
        self._screen(doc, result)
        return result

    # ------------------------------------------------------------------
    def _screen(self, doc: SourceDocument, result: CollectionResult) -> None:
        """★ 여기가 핵심 — 외부 도구가 가져온 것을 우리가 판정합니다."""
        self._seq += 1
        source_id = f"{result.collector}-{self._seq:05d}"

        verdict: FirewallVerdict = self.firewall.check(
            source_id=source_id,
            url=doc.url or f"internal://{result.collector}/{self._seq}",
            title=doc.title,
            body=doc.body,
            published=doc.published,
        )

        if not verdict.passed:
            result.rejected.append(RejectedDocument(
                url=doc.url, domain=doc.domain,
                reasons=verdict.reasons or ["필터링됨"],
                duplicate_of=verdict.is_duplicate_of,
            ))
            return

        # ★ 등급은 수집기 말이 아니라 우리 도메인 규칙으로 정합니다.
        tier = tier_of_domain(doc.url or doc.domain, self.config_dir)
        rule = rule_of(tier, self.config_dir)

        # 방화벽이 깎은 신뢰도와 등급 가중치 중 낮은 쪽을 취합니다.
        confidence = min(verdict.confidence, rule.weight)

        result.accepted.append(AcceptedDocument(
            document=doc,
            tier=tier,
            confidence=confidence,
            # 방화벽이 확정 자격을 박탈했으면 등급과 무관하게 박탈입니다.
            can_confirm_fact=rule.can_confirm_fact and verdict.can_confirm_fact,
            penalties=verdict.penalties,
            content_hash=verdict.content_hash,
        ))
