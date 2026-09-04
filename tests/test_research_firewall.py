"""Research Firewall + 근사 중복 + 소스 계보 테스트.

가장 위험한 실패는 '스팸을 통과시키는 것'과
'복사 기사 50건을 독립 근거 50건으로 세는 것'입니다.
"""

import unittest
from datetime import datetime, timedelta, timezone

from packages.source_validation.firewall import ResearchFirewall
from packages.source_validation.lineage import LineageTracker, SourceRecord
from packages.source_validation.simhash import (
    content_hash,
    hamming,
    is_near_duplicate,
    simhash,
)
from packages.source_validation.tiers import SourceTier, tier_of_domain

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

LEGIT = (
    "According to the 10-Q filed with the SEC, revenue was $4.2 billion for the "
    "quarter with gross margin of 61.3 percent. The filing discloses segment "
    "detail and capital expenditure figures. Management commentary in the same "
    "filing referenced existing supply agreements and contracted volumes."
)


class TestSimHash(unittest.TestCase):
    def test_identical_text_same_hash(self):
        self.assertEqual(simhash("hello world foo bar"), simhash("hello world foo bar"))

    def test_near_duplicate_detected(self):
        a = LEGIT
        b = LEGIT + " An additional sentence was appended by the aggregator."
        self.assertTrue(is_near_duplicate(simhash(a), simhash(b)))

    def test_different_text_not_duplicate(self):
        a = LEGIT
        b = ("Completely unrelated content about weather patterns in the north "
             "atlantic and shipping lane disruptions during winter storms.")
        self.assertFalse(is_near_duplicate(simhash(a), simhash(b)))

    def test_hamming_symmetric(self):
        x, y = simhash("alpha beta gamma"), simhash("alpha beta delta")
        self.assertEqual(hamming(x, y), hamming(y, x))

    def test_content_hash_normalizes_whitespace_and_case(self):
        self.assertEqual(content_hash("Hello   World"), content_hash("hello world"))


class TestTiers(unittest.TestCase):
    def test_official_sources_are_tier_s(self):
        self.assertEqual(tier_of_domain("https://www.sec.gov/x"), SourceTier.S)
        self.assertEqual(tier_of_domain("fda.gov"), SourceTier.S)

    def test_subdomain_resolves_to_parent(self):
        self.assertEqual(tier_of_domain("https://news.reuters.com/a"), SourceTier.A)

    def test_social_is_tier_e(self):
        self.assertEqual(tier_of_domain("https://www.reddit.com/r/x"), SourceTier.E)

    def test_unknown_domain(self):
        self.assertEqual(tier_of_domain("https://whatever.example.org"), SourceTier.UNKNOWN)


class TestFirewall(unittest.TestCase):
    def setUp(self):
        self.fw = ResearchFirewall()

    def test_legit_filing_passes(self):
        v = self.fw.check("s1", "https://www.sec.gov/a", "Quarterly report",
                          LEGIT, published=NOW - timedelta(days=2), now=NOW)
        self.assertTrue(v.passed)
        self.assertEqual(v.tier, SourceTier.S)
        self.assertTrue(v.can_confirm_fact)

    def test_pump_spam_blocked(self):
        body = ("충격! 이 종목 폭등 임박! 지금 사야 합니다! 세력이 들어왔다! "
                "작전주! 수익률 500% 가능! 이 기사는 보도자료를 기반으로 작성되었습니다.")
        v = self.fw.check("s2", "https://spam.example.com/x", "충격! 폭등 임박!",
                          body, published=NOW, now=NOW)
        self.assertFalse(v.passed)

    def test_ai_generated_spam_blocked(self):
        body = ("In today's fast-paced world, investors must delve into the world "
                "of equities. In conclusion, it is important to note that "
                "diversification matters a great deal for everyone involved.")
        v = self.fw.check("s3", "https://farm.example.com/x", "Investing guide",
                          body, published=NOW, now=NOW)
        self.assertFalse(v.passed)

    def test_exact_duplicate_blocked(self):
        self.fw.check("s4", "https://www.reuters.com/a", "T", LEGIT,
                      published=NOW, now=NOW)
        v = self.fw.check("s5", "https://copycat.example.com/a", "T", LEGIT,
                          published=NOW, now=NOW)
        self.assertFalse(v.passed)
        self.assertEqual(v.is_duplicate_of, "s4")

    def test_near_duplicate_blocked(self):
        """★ 이게 없으면 신디케이션 기사를 독립 근거로 세게 됩니다."""
        self.fw.check("orig", "https://www.reuters.com/a", "T", LEGIT,
                      published=NOW, now=NOW)
        v = self.fw.check(
            "copy", "https://aggregator.example.com/a", "T",
            LEGIT + " Additional context was provided by the aggregator site.",
            published=NOW, now=NOW,
        )
        self.assertFalse(v.passed)
        self.assertEqual(v.is_duplicate_of, "orig")

    def test_old_article_claiming_to_be_latest_blocked(self):
        v = self.fw.check("s6", "https://news.example.com/x", "BREAKING: latest",
                          LEGIT, published=NOW - timedelta(days=800),
                          now=NOW, claims_recent=True)
        self.assertFalse(v.passed)

    def test_unsourced_numbers_lower_confidence(self):
        body = ("The company grew revenue 47% last quarter and now holds 62% "
                "market share with margins expanding to 38% this year overall.")
        v = self.fw.check("s7", "https://blog.example.com/x", "Strong growth",
                          body, published=NOW, now=NOW)
        self.assertTrue(v.unsourced_numbers)
        self.assertFalse(v.can_confirm_fact)
        self.assertLess(v.confidence, 0.3)

    def test_rumor_cannot_confirm_fact(self):
        body = ("익명의 소식통에 따르면 대형 계약이 임박했다고 한다. "
                "업계 관계자는 익명을 전제로 규모가 상당하다고 전했다. "
                "회사 측은 공식 입장을 내놓지 않았다고 알려졌다.")
        v = self.fw.check("s8", "https://www.reuters.com/rumor", "계약설", body,
                          published=NOW, now=NOW)
        self.assertFalse(v.can_confirm_fact)

    def test_reset_clears_memory(self):
        self.fw.check("a", "https://www.sec.gov/a", "T", LEGIT, published=NOW, now=NOW)
        self.fw.reset()
        v = self.fw.check("b", "https://www.sec.gov/a", "T", LEGIT,
                          published=NOW, now=NOW)
        self.assertTrue(v.passed)


class TestLineage(unittest.TestCase):
    def test_fifty_copies_count_as_one_independent_source(self):
        """★ 프로젝트의 핵심 요구사항."""
        t = LineageTracker()
        t.add(SourceRecord("orig", "https://www.reuters.com/a", "reuters.com",
                           SourceTier.A))
        for i in range(50):
            t.add(SourceRecord(f"copy{i}", f"https://site{i}.example.com/a",
                               f"site{i}.example.com", SourceTier.D,
                               original_source_id="orig"))
        self.assertEqual(t.page_count, 51)
        self.assertEqual(t.independent_evidence_count, 1)

    def test_two_independent_sources_confirm(self):
        t = LineageTracker()
        t.add(SourceRecord("a", "https://www.sec.gov/a", "sec.gov", SourceTier.S))
        t.add(SourceRecord("b", "https://www.reuters.com/b", "reuters.com",
                           SourceTier.A))
        v = t.verdict()
        self.assertEqual(v["status"], "CONFIRMED_FACT")
        self.assertEqual(v["independent_evidence_count"], 2)

    def test_single_source_is_not_confirmed(self):
        t = LineageTracker()
        t.add(SourceRecord("a", "https://www.sec.gov/a", "sec.gov", SourceTier.S))
        self.assertEqual(t.verdict()["status"], "SINGLE_SOURCE")

    def test_low_tier_only_is_discovery_lead_not_discarded(self):
        """레딧 소문은 버리지 않되, 확정 사실도 되지 않습니다 (§24)."""
        t = LineageTracker()
        t.add(SourceRecord("r1", "https://www.reddit.com/a", "reddit.com",
                           SourceTier.E))
        t.add(SourceRecord("r2", "https://x.com/a", "x.com", SourceTier.E))
        v = t.verdict()
        self.assertEqual(v["status"], "DISCOVERY_LEAD")

    def test_no_sources(self):
        self.assertEqual(LineageTracker().verdict()["status"], "NO_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
