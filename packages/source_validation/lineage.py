"""Source Lineage — 독립 근거 수와 페이지 수를 분리합니다.

프로젝트 원칙 §23
    같은 로이터 원문을 50개 사이트가 복사했다고
    50개의 독립 출처로 계산하면 안 됩니다.

    page_count = 50
    independent_evidence_count = 1

    신뢰도 계산에는 후자만 씁니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .tiers import SourceTier, rule_of


@dataclass
class SourceRecord:
    source_id: str
    url: str
    domain: str
    tier: SourceTier
    title: str = ""
    published: str | None = None
    original_source_id: str | None = None   # 원문. None 이면 자기 자신이 원문
    confidence: float = 0.0

    @property
    def root_id(self) -> str:
        return self.original_source_id or self.source_id

    @property
    def is_independent(self) -> bool:
        return self.original_source_id is None


@dataclass
class LineageTracker:
    """한 주장(claim)에 붙은 근거들의 계보."""

    records: dict[str, SourceRecord] = field(default_factory=dict)

    def add(self, rec: SourceRecord) -> None:
        self.records[rec.source_id] = rec

    # ------------------------------------------------------------------
    @property
    def page_count(self) -> int:
        """읽은 페이지 수. 신뢰도 계산에 쓰면 안 되는 숫자."""
        return len(self.records)

    @property
    def independent_evidence_count(self) -> int:
        """서로 다른 원문의 개수. 이게 진짜 근거 수."""
        return len({r.root_id for r in self.records.values()})

    def independent_roots(self) -> dict[str, list[str]]:
        """원문별로 복사본을 묶어서 보여줍니다."""
        out: dict[str, list[str]] = {}
        for r in self.records.values():
            out.setdefault(r.root_id, []).append(r.source_id)
        return out

    def best_tier(self) -> SourceTier:
        order = [SourceTier.S, SourceTier.A, SourceTier.B,
                 SourceTier.C, SourceTier.D, SourceTier.E, SourceTier.UNKNOWN]
        present = {r.tier for r in self.records.values()}
        for t in order:
            if t in present:
                return t
        return SourceTier.UNKNOWN

    # ------------------------------------------------------------------
    def verdict(self, min_independent: int = 2, min_tier: SourceTier = SourceTier.B) -> dict:
        """확정 사실로 인정할 수 있는지 판정합니다 (§24, §25)."""
        order = {SourceTier.S: 0, SourceTier.A: 1, SourceTier.B: 2,
                 SourceTier.C: 3, SourceTier.D: 4, SourceTier.E: 5, SourceTier.UNKNOWN: 6}

        confirmable = [
            r for r in self.records.values()
            if rule_of(r.tier).can_confirm_fact and order[r.tier] <= order[min_tier]
        ]
        independent_confirmable = len({r.root_id for r in confirmable})

        if independent_confirmable >= min_independent:
            status = "CONFIRMED_FACT"
        elif independent_confirmable == 1:
            status = "SINGLE_SOURCE"
        elif self.records:
            status = "DISCOVERY_LEAD"   # 버리지 않고 조사 단서로 남깁니다
        else:
            status = "NO_EVIDENCE"

        return {
            "status": status,
            "page_count": self.page_count,
            "independent_evidence_count": self.independent_evidence_count,
            "independent_confirmable_count": independent_confirmable,
            "best_tier": self.best_tier().value,
            "roots": self.independent_roots(),
            "note": (
                "page_count 는 신뢰도 계산에 사용하지 않습니다. "
                "복사 기사 50건은 독립 근거 1건입니다."
            ),
        }
