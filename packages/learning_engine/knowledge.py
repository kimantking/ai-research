"""지식 승인 파이프라인.

프로젝트 원칙 §31
    에이전트가 읽었다고 바로 Knowledge 가 되지 않습니다.

    Knowledge Candidate
        → Source Check → Duplicate Check → Contradiction Check
        → Evidence Check → Validation → Approved Knowledge

    검증에 실패한 것도 Rejected 에 저장합니다.
    같은 거짓 정보가 다시 들어오면 과거 기록을 대조합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from packages.source_validation.lineage import LineageTracker, SourceRecord
from packages.source_validation.simhash import content_hash, hamming, simhash
from packages.source_validation.tiers import SourceTier, rule_of


class VerificationOutcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_RESEARCH = "NEEDS_MORE_RESEARCH"


@dataclass
class KnowledgeCandidate:
    statement: str
    agent_id: str
    sources: list[SourceRecord] = field(default_factory=list)
    numeric_claims: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.numeric_claims:
            self.numeric_claims = re.findall(
                r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s*(?:%|억|조|billion|million|B|M|배)",
                self.statement,
            )


@dataclass
class ApprovedKnowledge:
    k_id: str
    statement: str
    agent_id: str
    confidence: float
    evidence_status: str
    independent_evidence_count: int
    best_tier: str
    simhash: int
    approved_at: str


@dataclass
class RejectedKnowledge:
    statement: str
    agent_id: str
    reasons: list[str]
    simhash: int
    rejected_at: str
    times_seen: int = 1


class KnowledgeStore:
    """승인된 지식과 기각된 지식을 함께 보관합니다."""

    def __init__(self, min_independent: int = 2, min_tier: SourceTier = SourceTier.B):
        self.min_independent = min_independent
        self.min_tier = min_tier
        self.approved: dict[str, ApprovedKnowledge] = {}
        self.rejected: list[RejectedKnowledge] = []
        self._approved_sims: list[tuple[int, str]] = []

    # ------------------------------------------------------------------
    def submit(self, cand: KnowledgeCandidate) -> tuple[VerificationOutcome, dict]:
        reasons: list[str] = []
        checks: dict = {}
        sh = simhash(cand.statement)

        # ---- 0) 과거에 기각된 적 있는 주장인가 ----
        for rej in self.rejected:
            if hamming(rej.simhash, sh) <= 6:
                rej.times_seen += 1
                checks["previously_rejected"] = {
                    "times_seen": rej.times_seen,
                    "original_reasons": rej.reasons,
                }
                reasons.append(
                    f"과거에 기각된 주장과 거의 동일 (총 {rej.times_seen}회 유입). "
                    f"기존 기각 사유: {'; '.join(rej.reasons[:2])}"
                )
                return VerificationOutcome.REJECTED, {"checks": checks, "reasons": reasons}

        # ---- 1) 소스 존재 여부 ----
        if not cand.sources:
            reasons.append("근거 출처가 하나도 없습니다 (NO EVIDENCE = NO CLAIM)")
            self._reject(cand, reasons, sh)
            return VerificationOutcome.REJECTED, {"checks": checks, "reasons": reasons}

        # ---- 2) 계보 / 독립 근거 수 ----
        tracker = LineageTracker()
        for s in cand.sources:
            tracker.add(s)
        lineage = tracker.verdict(self.min_independent, self.min_tier)
        checks["lineage"] = lineage

        # ---- 3) 중복 (이미 아는 지식인가) ----
        for h, kid in self._approved_sims:
            if hamming(h, sh) <= 5:
                checks["duplicate_of"] = kid
                reasons.append(f"이미 보유한 지식과 중복 ({kid})")
                return VerificationOutcome.REJECTED, {"checks": checks, "reasons": reasons}

        # ---- 4) 숫자 근거 검사 (§25) ----
        confirmable_sources = [s for s in cand.sources if rule_of(s.tier).can_confirm_fact]
        if cand.numeric_claims and not confirmable_sources:
            reasons.append(
                f"수치 {len(cand.numeric_claims)}개가 포함되어 있으나 "
                "확정 근거가 될 수 있는 등급의 출처가 없습니다"
            )
            checks["numeric_claims"] = cand.numeric_claims
            self._reject(cand, reasons, sh)
            return VerificationOutcome.REJECTED, {"checks": checks, "reasons": reasons}

        # ---- 5) 최종 판정 ----
        status = lineage["status"]
        if status == "CONFIRMED_FACT":
            k_id = f"k{len(self.approved) + 1:05d}"
            weights = [rule_of(s.tier).weight for s in cand.sources]
            conf = min(0.98, max(weights) * 0.7 + min(1.0, lineage["independent_evidence_count"] / 3) * 0.3)
            self.approved[k_id] = ApprovedKnowledge(
                k_id=k_id,
                statement=cand.statement,
                agent_id=cand.agent_id,
                confidence=round(conf, 3),
                evidence_status=status,
                independent_evidence_count=lineage["independent_evidence_count"],
                best_tier=lineage["best_tier"],
                simhash=sh,
                approved_at=datetime.now(timezone.utc).isoformat(),
            )
            self._approved_sims.append((sh, k_id))
            return VerificationOutcome.APPROVED, {"checks": checks, "k_id": k_id}

        if status in ("SINGLE_SOURCE", "DISCOVERY_LEAD"):
            reasons.append(
                f"독립 근거 부족 (독립 근거 {lineage['independent_evidence_count']}개, "
                f"최소 {self.min_independent}개 필요) — 폐기하지 않고 추가 조사 대상으로 남깁니다"
            )
            return VerificationOutcome.NEEDS_MORE_RESEARCH, {"checks": checks, "reasons": reasons}

        reasons.append("유효한 근거 없음")
        self._reject(cand, reasons, sh)
        return VerificationOutcome.REJECTED, {"checks": checks, "reasons": reasons}

    # ------------------------------------------------------------------
    def _reject(self, cand: KnowledgeCandidate, reasons: list[str], sh: int) -> None:
        self.rejected.append(
            RejectedKnowledge(
                statement=cand.statement,
                agent_id=cand.agent_id,
                reasons=list(reasons),
                simhash=sh,
                rejected_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def stats(self) -> dict:
        return {
            "approved": len(self.approved),
            "rejected": len(self.rejected),
            "repeat_offenders": sum(1 for r in self.rejected if r.times_seen > 1),
        }
