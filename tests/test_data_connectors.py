"""수집기 + 파이프라인 테스트.

★ 여기서 증명하려는 것
   "외부 수집 도구를 붙여도 우리 판정 규칙이 그대로 살아 있다"

   Agent Reach 가 레딧에서 가져왔든 SEC 에서 가져왔든,
   등급과 통과 여부는 우리가 정합니다.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packages.data_connectors.agent_reach import (
    COOKIE_CHANNELS,
    ZERO_CONFIG_CHANNELS,
    AgentReachCollector,
    _domain_of,
    _parse_time,
)
from packages.data_connectors.base import (
    CollectorHealth,
    CollectorStatus,
    SourceDocument,
)
from packages.data_connectors.pipeline import CollectionPipeline
from packages.source_validation.tiers import SourceTier

CONFIG = Path(__file__).resolve().parents[1] / "config"
NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)

FILING = (
    "According to the 10-Q filed with the SEC, revenue was $4.2 billion for the "
    "quarter with gross margin of 61.3 percent. The filing discloses segment "
    "detail and capital expenditure figures. Management commentary in the same "
    "filing referenced existing supply agreements and contracted volumes."
)
SPAM = (
    "충격! 이 종목 폭등 임박! 지금 사야 합니다! 세력이 들어왔다! "
    "작전주! 수익률 500% 가능! 이 기사는 보도자료를 기반으로 작성되었습니다."
)


# ====================================================================== 가짜 수집기


class FakeCollector:
    """테스트용. 실제 네트워크를 쓰지 않습니다."""

    collector_id = "fake"

    def __init__(self, docs: list[SourceDocument],
                 status: CollectorStatus = CollectorStatus.CONNECTED):
        self.docs = docs
        self.status = status

    def health(self) -> CollectorHealth:
        return CollectorHealth("fake", "Fake", self.status, "테스트용")

    def read(self, url: str, timeout: float = 30.0):
        return self.docs[0] if self.docs else None

    def search(self, query: str, channel: str = "web",
               limit: int = 10, timeout: float = 60.0):
        return self.docs[:limit]


def doc(url: str, body: str, title: str = "T",
        published: datetime | None = None) -> SourceDocument:
    return SourceDocument(
        url=url, title=title, body=body, domain=_domain_of(url),
        channel="web", published=published or NOW - timedelta(days=1),
        collector="fake",
    )


# ====================================================================== 어댑터


class TestAgentReachAdapter(unittest.TestCase):
    def setUp(self):
        self.c = AgentReachCollector(config_dir=CONFIG)

    def test_not_installed_is_not_an_error(self):
        """설치되지 않은 것은 오류가 아닙니다. 조용히 비활성화됩니다."""
        h = self.c.health()
        self.assertIn(h.status, (CollectorStatus.NOT_INSTALLED,
                                 CollectorStatus.CONNECTED,
                                 CollectorStatus.DISABLED))
        if h.status is CollectorStatus.NOT_INSTALLED:
            self.assertIn("정상 동작", h.detail)

    def test_never_auto_installs(self):
        """★ 자동 설치는 절대 금지입니다 (자격증명이 걸린 행위)."""
        self.assertFalse(self.c._cfg.get("auto_install", False))
        src = (Path(__file__).resolve().parents[1]
               / "packages" / "data_connectors" / "agent_reach.py"
               ).read_text(encoding="utf-8")
        for forbidden in ("pipx install", "pip install", "--system"):
            self.assertNotIn(forbidden, src,
                             f"어댑터가 설치 명령을 실행하려 합니다: {forbidden}")

    def test_cookie_channels_blocked_by_default(self):
        """쿠키 채널은 기본 차단 — 약관 위반·계정 정지 위험."""
        for ch in ("twitter", "instagram", "linkedin", "xiaohongshu"):
            ok, why = self.c.channel_allowed(ch)
            self.assertFalse(ok, f"{ch} 가 기본 허용되어 있습니다")
            self.assertIn("쿠키", why)

    def test_zero_config_channels_allowed(self):
        for ch in ("web", "rss", "youtube", "github"):
            ok, _ = self.c.channel_allowed(ch)
            self.assertTrue(ok, f"{ch} 가 막혀 있습니다")

    def test_channel_sets_do_not_overlap(self):
        self.assertEqual(ZERO_CONFIG_CHANNELS & COOKIE_CHANNELS, set())

    def test_search_returns_empty_when_not_installed(self):
        if self.c.find_executable() is None:
            self.assertEqual(self.c.search("NVDA"), [])
            self.assertIsNone(self.c.read("https://example.com"))

    def test_collected_documents_start_unverified(self):
        d = self.c._item_to_document(
            {"url": "https://www.sec.gov/x", "title": "T", "content": "body"}, "web")
        self.assertIsNotNone(d)
        self.assertFalse(d.verified, "수집 단계에서 검증됨으로 표시하면 안 됩니다")

    def test_parses_json_list_and_jsonlines(self):
        as_list = self.c._parse_items('[{"url":"https://a.com"},{"url":"https://b.com"}]')
        self.assertEqual(len(as_list), 2)
        as_lines = self.c._parse_items('{"url":"https://a.com"}\n{"url":"https://b.com"}')
        self.assertEqual(len(as_lines), 2)
        wrapped = self.c._parse_items('{"results":[{"url":"https://a.com"}]}')
        self.assertEqual(len(wrapped), 1)

    def test_malformed_output_does_not_crash(self):
        self.assertEqual(self.c._parse_items("<<not json>>"), [])
        self.assertEqual(self.c._parse_items(""), [])

    def test_domain_extraction(self):
        self.assertEqual(_domain_of("https://www.Reuters.com/a?b=1"), "reuters.com")
        self.assertEqual(_domain_of("https://news.sec.gov/x"), "news.sec.gov")
        self.assertEqual(_domain_of(""), "")

    def test_time_parsing(self):
        self.assertIsNotNone(_parse_time("2026-09-01"))
        self.assertIsNotNone(_parse_time("2026-09-01T10:00:00Z"))
        self.assertIsNotNone(_parse_time(1_750_000_000))
        self.assertIsNone(_parse_time("어제쯤?"))
        self.assertIsNone(_parse_time(None))


# ====================================================================== 파이프라인


class TestCollectionPipeline(unittest.TestCase):
    """★ 핵심: 외부 도구가 가져와도 우리 방화벽이 판정합니다."""

    def _pipe(self, docs, status=CollectorStatus.CONNECTED):
        return CollectionPipeline(FakeCollector(docs, status), config_dir=CONFIG)

    def test_spam_is_rejected_even_from_collector(self):
        p = self._pipe([doc("https://pump.example.com/x", SPAM, "충격! 폭등 임박!")])
        r = p.collect("NVDA")
        self.assertEqual(len(r.accepted), 0)
        self.assertEqual(len(r.rejected), 1)

    def test_legit_filing_accepted_as_tier_s(self):
        p = self._pipe([doc("https://www.sec.gov/Archives/x.htm", FILING)])
        r = p.collect("NVDA")
        self.assertEqual(len(r.accepted), 1)
        self.assertEqual(r.accepted[0].tier, SourceTier.S)
        self.assertTrue(r.accepted[0].can_confirm_fact)

    def test_reddit_stays_tier_e_regardless_of_collector(self):
        """★ 'Agent Reach 로 가져왔으니 믿을 만하다' 는 성립하지 않습니다."""
        body = ("The company appears to be doing well based on what people are "
                "posting here about the recent product launch and general vibes "
                "in the community over the past several weeks of discussion.")
        p = self._pipe([doc("https://www.reddit.com/r/stocks/x", body)])
        r = p.collect("NVDA", channel="web")
        self.assertEqual(len(r.accepted), 1)
        self.assertEqual(r.accepted[0].tier, SourceTier.E)
        self.assertFalse(r.accepted[0].can_confirm_fact,
                         "레딧이 확정 사실 자격을 가지면 안 됩니다")

    def test_near_duplicate_across_collected_docs_rejected(self):
        p = self._pipe([
            doc("https://www.reuters.com/a", FILING),
            doc("https://aggregator.example.com/a",
                FILING + " Additional context was added by the aggregator."),
        ])
        r = p.collect("NVDA")
        self.assertEqual(len(r.accepted), 1)
        self.assertEqual(len(r.rejected), 1)
        self.assertIsNotNone(r.rejected[0].duplicate_of)

    def test_page_count_and_independent_count_are_separate(self):
        p = self._pipe([
            doc("https://www.sec.gov/a", FILING),
            doc("https://www.reuters.com/b", FILING.replace("4.2", "4.3")),
        ])
        r = p.collect("NVDA").to_dict()
        self.assertIn("page_count", r)
        self.assertIn("independent_evidence_count", r)
        self.assertIn("복사 기사", r["note"])

    def test_confidence_never_exceeds_tier_weight(self):
        p = self._pipe([doc("https://medium.com/x", FILING)])
        r = p.collect("NVDA")
        if r.accepted:
            self.assertLessEqual(r.accepted[0].confidence, 0.20 + 1e-9,
                                 "Tier D 가중치를 넘는 신뢰도가 나왔습니다")

    def test_unsourced_numbers_lose_confirm_right(self):
        body = ("The company grew revenue 47% last quarter and now holds 62% "
                "market share with margins expanding to 38% this year overall.")
        p = self._pipe([doc("https://www.reuters.com/x", body)])
        r = p.collect("NVDA")
        if r.accepted:
            self.assertFalse(r.accepted[0].can_confirm_fact)

    def test_pipeline_survives_missing_collector(self):
        """수집기가 없어도 시스템은 멈추지 않습니다."""
        p = self._pipe([], status=CollectorStatus.NOT_INSTALLED)
        r = p.collect("NVDA")
        self.assertEqual(r.collected, 0)
        self.assertIn("정상 동작", r.note)

    def test_accepted_doc_converts_to_source_record(self):
        p = self._pipe([doc("https://www.sec.gov/a", FILING)])
        r = p.collect("NVDA")
        rec = r.accepted[0].as_source_record("s1")
        self.assertEqual(rec.tier, SourceTier.S)
        self.assertTrue(rec.is_independent)


class TestAgentReachConfig(unittest.TestCase):
    def test_config_file_exists_and_is_safe(self):
        cfg = CONFIG / "data_sources" / "agent_reach.yaml"
        self.assertTrue(cfg.exists())
        text = cfg.read_text(encoding="utf-8")
        self.assertIn("auto_install: false", text)
        self.assertIn("allow_cookie_channels: false", text)

    def test_install_script_has_no_system_flag(self):
        """--system 은 시스템 전역 설정을 바꿉니다. 쓰지 않습니다.

        주석에 "--system 을 쓰지 않는다"고 적는 것은 허용되므로,
        실제로 실행되는 줄만 검사합니다.
        """
        from tests.test_scripts_safety import executable_lines

        path = (Path(__file__).resolve().parents[1]
                / "scripts" / "install-agent-reach.ps1")
        for s in executable_lines(path).splitlines():
            if s.startswith("Write-"):        # 화면 출력 문구는 명령이 아님
                continue
            self.assertNotIn("--system", s,
                             f"설치 스크립트가 --system 을 씁니다: {s}")

    def test_install_script_asks_for_consent(self):
        script = (Path(__file__).resolve().parents[1]
                  / "scripts" / "install-agent-reach.ps1"
                  ).read_text(encoding="utf-8")
        self.assertIn("Read-Host", script, "동의 프롬프트가 없습니다")
        self.assertIn("약관", script, "약관 위험 경고가 없습니다")


if __name__ == "__main__":
    unittest.main()
