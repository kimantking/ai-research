"""Evidence Gate + 지식 승인 파이프라인 테스트.

"근거 없는 숫자를 쓰지 마세요"를 부탁이 아니라 강제로 만든 부분입니다.
그 강제가 실제로 동작하는지 확인합니다.
"""

import unittest

from packages.evaluation.evidence_gate import EvidenceGate, EvidenceMissing
from packages.learning_engine.knowledge import (
    KnowledgeCandidate,
    KnowledgeStore,
    VerificationOutcome,
)
from packages.source_validation.lineage import SourceRecord
from packages.source_validation.tiers import SourceTier


class TestEvidenceGate(unittest.TestCase):
    def test_number_without_evidence_is_blocked(self):
        gate = EvidenceGate(strict=True)
        with self.assertRaises(EvidenceMissing):
            gate.enforce("매출이 47% 증가했습니다.")

    def test_number_with_evidence_passes(self):
        gate = EvidenceGate(known_evidence_ids={"EV001"}, strict=True)
        text = "매출이 47% 증가했습니다. [E:EV001]"
        self.assertEqual(gate.enforce(text), text)

    def test_bare_decimal_is_also_checked(self):
        """단위 없는 숫자(지지선 182.45)가 제일 위험합니다."""
        rep = EvidenceGate().check("지지선은 182.45 입니다.")
        self.assertFalse(rep.passed)
        self.assertEqual(rep.checked_numbers, 1)

    def test_unknown_evidence_id_is_blocked(self):
        gate = EvidenceGate(known_evidence_ids={"EV001"})
        rep = gate.check("매출이 47% 증가했습니다. [E:EV999]")
        self.assertFalse(rep.passed)
        self.assertIn("EV999", rep.unknown_evidence_ids)

    def test_text_without_numbers_passes(self):
        rep = EvidenceGate().check("추세가 상승으로 전환되었습니다.")
        self.assertTrue(rep.passed)
        self.assertEqual(rep.checked_numbers, 0)

    def test_evidence_tag_itself_is_not_counted_as_number(self):
        gate = EvidenceGate(known_evidence_ids={"EV001"})
        rep = gate.check("추세는 상승입니다. [E:EV001]")
        self.assertTrue(rep.passed)
        self.assertEqual(rep.checked_numbers, 0)

    def test_dates_are_not_counted(self):
        rep = EvidenceGate().check("보고일은 2026-09-01 입니다.")
        self.assertTrue(rep.passed)

    def test_each_sentence_checked_separately(self):
        """한 문장에 근거를 달았다고 다른 문장까지 통과시키면 안 됩니다."""
        gate = EvidenceGate(known_evidence_ids={"EV001"})
        rep = gate.check("매출은 47% 증가했습니다. [E:EV001]\n영업이익률은 38% 입니다.")
        self.assertFalse(rep.passed)
        self.assertEqual(len(rep.offenders), 1)


def _src(sid, domain, tier, original=None):
    return SourceRecord(sid, f"https://{domain}/x", domain, tier,
                        original_source_id=original)


class TestKnowledgeStore(unittest.TestCase):
    def setUp(self):
        self.store = KnowledgeStore()

    def test_no_source_is_rejected(self):
        out, _ = self.store.submit(
            KnowledgeCandidate("어떤 주장", "agent1", sources=[])
        )
        self.assertEqual(out, VerificationOutcome.REJECTED)

    def test_two_independent_high_tier_sources_approved(self):
        out, info = self.store.submit(KnowledgeCandidate(
            "해당 기업이 신규 공급계약을 공시했다", "agent1",
            sources=[_src("a", "sec.gov", SourceTier.S),
                     _src("b", "reuters.com", SourceTier.A)],
        ))
        self.assertEqual(out, VerificationOutcome.APPROVED)
        self.assertIn("k_id", info)

    def test_single_source_needs_more_research_not_discarded(self):
        out, _ = self.store.submit(KnowledgeCandidate(
            "단일 출처 주장입니다", "agent1",
            sources=[_src("a", "sec.gov", SourceTier.S)],
        ))
        self.assertEqual(out, VerificationOutcome.NEEDS_MORE_RESEARCH)

    def test_syndicated_copies_do_not_confirm(self):
        """같은 원문 복사본 여러 개로는 확정 사실이 되지 않습니다."""
        out, info = self.store.submit(KnowledgeCandidate(
            "복사 기사만 여러 건인 주장", "agent1",
            sources=[
                _src("orig", "reuters.com", SourceTier.A),
                _src("c1", "aggr1.com", SourceTier.A, original="orig"),
                _src("c2", "aggr2.com", SourceTier.A, original="orig"),
            ],
        ))
        self.assertEqual(out, VerificationOutcome.NEEDS_MORE_RESEARCH)
        self.assertEqual(info["checks"]["lineage"]["independent_evidence_count"], 1)
        self.assertEqual(info["checks"]["lineage"]["page_count"], 3)

    def test_numeric_claim_without_confirmable_source_rejected(self):
        out, _ = self.store.submit(KnowledgeCandidate(
            "매출이 47% 증가했다", "agent1",
            sources=[_src("r", "reddit.com", SourceTier.E)],
        ))
        self.assertEqual(out, VerificationOutcome.REJECTED)

    def test_rejected_knowledge_is_remembered(self):
        """같은 거짓 정보가 다시 들어오면 과거 기록을 대조합니다 (§31)."""
        cand = KnowledgeCandidate("근거 없는 주장", "agent1", sources=[])
        self.store.submit(cand)
        out, info = self.store.submit(
            KnowledgeCandidate("근거 없는 주장", "agent2", sources=[])
        )
        self.assertEqual(out, VerificationOutcome.REJECTED)
        self.assertIn("previously_rejected", info["checks"])
        self.assertEqual(info["checks"]["previously_rejected"]["times_seen"], 2)

    def test_duplicate_of_approved_knowledge_rejected(self):
        srcs = [_src("a", "sec.gov", SourceTier.S), _src("b", "reuters.com", SourceTier.A)]
        self.store.submit(KnowledgeCandidate("동일한 사실 진술입니다", "a1", sources=srcs))
        out, info = self.store.submit(
            KnowledgeCandidate("동일한 사실 진술입니다", "a2",
                               sources=[_src("c", "sec.gov", SourceTier.S),
                                        _src("d", "wsj.com", SourceTier.A)])
        )
        self.assertEqual(out, VerificationOutcome.REJECTED)
        self.assertIn("duplicate_of", info["checks"])

    def test_stats(self):
        self.store.submit(KnowledgeCandidate("근거 없음", "a", sources=[]))
        s = self.store.stats()
        self.assertEqual(s["rejected"], 1)
        self.assertEqual(s["approved"], 0)


if __name__ == "__main__":
    unittest.main()
