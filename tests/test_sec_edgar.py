"""SEC EDGAR 수집기 검증 (Phase 12).

★ 핵심 검증 대상
   1. filing_date 와 period_of_report 를 절대 섞지 않는가 (look-ahead 방지)
   2. User-Agent 에 이메일이 없으면 **요청 자체를 만들지 않는가**
   3. 초당 10요청 제한을 실제로 지키는가
"""

import json
import unittest

from packages.sec_edgar import EdgarClient, EdgarError, RateLimiter
from packages.sec_edgar.filings import (
    ParseError,
    facts_as_pit_records,
    parse_company_facts,
    parse_submissions,
)

# ---- 실제 EDGAR 응답 형식 (구조 그대로, 값은 축약) ----
SUBMISSIONS = json.dumps({
    "cik": "320193",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "sicDescription": "Electronic Computers",
    "filings": {
        "recent": {
            "accessionNumber": ["0000320193-24-000123",
                                "0000320193-24-000081",
                                "0000320193-24-000070"],
            "form": ["10-K", "10-Q", "8-K"],
            "filingDate": ["2024-11-01", "2024-08-02", "2024-08-01"],
            "reportDate": ["2024-09-28", "2024-06-29", ""],
            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm",
                                "ex-99_1.htm"],
            "items": ["", "", "2.02,9.01"],
        }
    },
}).encode()

COMPANY_FACTS = json.dumps({
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "label": "Revenues",
                "units": {
                    "USD": [
                        {"start": "2024-06-30", "end": "2024-09-28",
                         "val": 94930000000, "fy": 2024, "fp": "Q4",
                         "form": "10-K", "filed": "2024-11-01"},
                        {"start": "2024-03-31", "end": "2024-06-29",
                         "val": 85777000000, "fy": 2024, "fp": "Q3",
                         "form": "10-Q", "filed": "2024-08-02"},
                        {"start": "2024-01-01", "end": "2024-03-30",
                         "val": 90753000000},          # ★ filed 없음 → 버려야 함
                    ]
                },
            }
        }
    },
}).encode()


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, headers=None, timeout=30.0):
        self.calls.append((url, headers or {}))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeClock:
    """시간을 우리가 조종합니다 — 테스트가 실제로 기다리지 않도록."""

    def __init__(self):
        self.t = 0.0
        self.slept = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self.slept += seconds


# ====================================================================== 파싱
class TestParseSubmissions(unittest.TestCase):
    def test_columns_become_rows(self):
        meta, filings = parse_submissions(SUBMISSIONS)
        self.assertEqual(meta["name"], "Apple Inc.")
        self.assertEqual(meta["cik"], "0000320193")
        self.assertEqual(meta["tickers"], ["AAPL"])
        self.assertEqual(len(filings), 3)
        self.assertEqual(filings[0].form, "10-K")

    def test_the_two_dates_are_kept_separate(self):
        """★ 이 프로젝트에서 가장 중요한 구분입니다."""
        _, filings = parse_submissions(SUBMISSIONS)
        f = filings[0]
        self.assertEqual(f.period_of_report, "2024-09-28")   # 실적 기간
        self.assertEqual(f.filing_date, "2024-11-01")        # 공개된 날
        self.assertNotEqual(f.period_of_report, f.filing_date)

    def test_reporting_lag_is_computed(self):
        _, filings = parse_submissions(SUBMISSIONS)
        # 9/28 → 11/1 = 34일. 이 34일이 곧 look-ahead 이득입니다.
        self.assertEqual(filings[0].reporting_lag_days, 34)

    def test_filing_without_report_date_is_ok(self):
        _, filings = parse_submissions(SUBMISSIONS)
        eight_k = filings[2]
        self.assertEqual(eight_k.form, "8-K")
        self.assertEqual(eight_k.period_of_report, "")
        self.assertIsNone(eight_k.reporting_lag_days)

    def test_url_is_built_correctly(self):
        _, filings = parse_submissions(SUBMISSIONS)
        url = filings[0].url()
        self.assertTrue(url.startswith("https://www.sec.gov/Archives/edgar/data/320193/"))
        self.assertIn("000032019324000123", url)
        self.assertTrue(url.endswith("aapl-20240928.htm"))

    def test_to_dict_carries_the_pit_warning(self):
        _, filings = parse_submissions(SUBMISSIONS)
        d = filings[0].to_dict()
        self.assertIn("filing_date", d["pit_note"])
        self.assertIn("period_of_report", d["pit_note"])

    def test_broken_json_raises_clearly(self):
        with self.assertRaises(ParseError):
            parse_submissions(b"not json")

    def test_empty_filings_is_not_an_error(self):
        meta, filings = parse_submissions(json.dumps(
            {"cik": "1", "name": "X", "filings": {"recent": {}}}).encode())
        self.assertEqual(filings, [])
        self.assertEqual(meta["name"], "X")

    def test_ragged_columns_do_not_crash(self):
        payload = json.dumps({
            "cik": "1", "name": "X",
            "filings": {"recent": {
                "accessionNumber": ["a", "b"],
                "form": ["10-K", "10-Q"],
                "filingDate": ["2024-01-01", "2024-02-01"],
                "reportDate": ["2023-12-31"],     # 하나 모자람
            }},
        }).encode()
        _, filings = parse_submissions(payload)
        self.assertEqual(len(filings), 2)
        self.assertEqual(filings[1].period_of_report, "")


class TestParseCompanyFacts(unittest.TestCase):
    def test_parses_facts(self):
        cf = parse_company_facts(COMPANY_FACTS)
        self.assertEqual(cf.name, "Apple Inc.")
        self.assertEqual(cf.cik, "0000320193")
        self.assertEqual(len(cf.facts), 2)

    def test_drops_facts_without_a_filed_date(self):
        """★ 언제 알 수 있었는지 모르는 값은 쓰면 안 됩니다."""
        cf = parse_company_facts(COMPANY_FACTS)
        self.assertEqual(getattr(cf, "facts_dropped_no_filed", 0), 1)
        self.assertTrue(all(f["filed"] for f in cf.facts))

    def test_facts_are_sorted_by_filed_date(self):
        cf = parse_company_facts(COMPANY_FACTS)
        filed = [f["filed"] for f in cf.facts]
        self.assertEqual(filed, sorted(filed))

    def test_period_end_and_filed_are_both_kept(self):
        cf = parse_company_facts(COMPANY_FACTS)
        q4 = [f for f in cf.facts if f["fiscal_period"] == "Q4"][0]
        self.assertEqual(q4["period_end"], "2024-09-28")
        self.assertEqual(q4["filed"], "2024-11-01")


class TestPitRecords(unittest.TestCase):
    def test_published_time_is_the_filing_date(self):
        """★ published_time 이 period_end 면 미래를 보게 됩니다."""
        cf = parse_company_facts(COMPANY_FACTS)
        recs = facts_as_pit_records(cf, "AAPL")
        self.assertTrue(recs)
        for r in recs:
            self.assertGreaterEqual(r["published_time"], r["event_time"])

    def test_revenue_is_invisible_before_the_filing(self):
        from packages.pit_store.store import PITStore, Record

        cf = parse_company_facts(COMPANY_FACTS)
        pit = PITStore()
        for r in facts_as_pit_records(cf, "AAPL"):
            pit.put_fact(Record(
                key=r["key"], value=r["value"],
                event_time=r["event_time"], published_time=r["published_time"],
                source_id=r["source_id"],
            ))
        key = "AAPL:Revenues:2024-09-28"
        period_end = 1727481600      # 2024-09-28
        filed = 1730419200           # 2024-11-01

        # 분기말 다음날에는 아직 매출을 알 수 없습니다
        self.assertIsNone(pit.get_fact(key, period_end + 86400))
        # 공시 다음날에는 알 수 있습니다
        rec = pit.get_fact(key, filed + 86400)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.value, 94930000000)


# ====================================================================== 속도제한
class TestRateLimiter(unittest.TestCase):
    def test_allows_burst_up_to_limit(self):
        clock = FakeClock()
        rl = RateLimiter(10, sleeper=clock.sleep, clock=clock.now)
        for _ in range(10):
            self.assertEqual(rl.acquire(), 0.0)
        self.assertEqual(clock.slept, 0.0)

    def test_eleventh_call_waits(self):
        clock = FakeClock()
        rl = RateLimiter(10, sleeper=clock.sleep, clock=clock.now)
        for _ in range(10):
            rl.acquire()
        waited = rl.acquire()
        self.assertGreater(waited, 0.9)

    def test_never_exceeds_limit_in_any_one_second_window(self):
        """★ '평균 10회'가 아니라 '어느 1초 구간에서도 10회 이하'."""
        clock = FakeClock()
        rl = RateLimiter(10, sleeper=clock.sleep, clock=clock.now)
        stamps = []
        for _ in range(35):
            rl.acquire()
            stamps.append(clock.now())
        for i, t in enumerate(stamps):
            in_window = sum(1 for s in stamps if t - 1.0 < s <= t)
            self.assertLessEqual(in_window, 10, f"{i}번째에서 1초 안에 {in_window}회")

    def test_rejects_bad_config(self):
        with self.assertRaises(ValueError):
            RateLimiter(0)


# ====================================================================== 클라이언트
class TestEdgarClient(unittest.TestCase):
    def test_refuses_to_request_without_contact_email(self):
        """★ 이메일 없이 보내면 차단됩니다. 아예 보내지 않습니다."""
        t = FakeTransport(SUBMISSIONS)
        c = EdgarClient(contact_email="", transport=t)
        res = c.fetch_filings("320193")
        self.assertFalse(res["ok"])
        self.assertIn("SEC_CONTACT_EMAIL", res["error"])
        self.assertEqual(t.calls, [], "요청을 보내면 안 됩니다")

    def test_rejects_malformed_email(self):
        c = EdgarClient(contact_email="not-an-email")
        self.assertFalse(c.configured)
        with self.assertRaises(EdgarError):
            c.user_agent()

    def test_sends_user_agent_with_email(self):
        t = FakeTransport(SUBMISSIONS)
        c = EdgarClient(contact_email="me@example.com", transport=t)
        c.fetch_filings("320193")
        _, headers = t.calls[0]
        self.assertIn("me@example.com", headers["User-Agent"])

    def test_url_shapes(self):
        c = EdgarClient(contact_email="me@example.com")
        self.assertEqual(c.submissions_url(320193),
                         "https://data.sec.gov/submissions/CIK0000320193.json")
        self.assertEqual(
            c.company_facts_url("320193"),
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json")

    def test_cik_normalization(self):
        self.assertEqual(EdgarClient.normalize_cik("CIK0000320193"), "0000320193")
        self.assertEqual(EdgarClient.normalize_cik(320193), "0000320193")
        with self.assertRaises(EdgarError):
            EdgarClient.normalize_cik("abc")

    def test_form_filter(self):
        t = FakeTransport(SUBMISSIONS)
        c = EdgarClient(contact_email="me@example.com", transport=t)
        res = c.fetch_filings("320193", forms=("10-K",))
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["filings"][0]["form"], "10-K")

    def test_network_error_is_reported_not_raised(self):
        c = EdgarClient(contact_email="me@example.com",
                        transport=FakeTransport(RuntimeError("HTTP 429")))
        res = c.fetch_filings("320193")
        self.assertFalse(res["ok"])
        self.assertIn("429", res["error"])
        self.assertEqual(c.stats.errors, 1)

    def test_company_facts_flow(self):
        c = EdgarClient(contact_email="me@example.com",
                        transport=FakeTransport(COMPANY_FACTS))
        res = c.fetch_company_facts("320193", "AAPL")
        self.assertTrue(res["ok"])
        self.assertEqual(res["fact_count"], 2)
        self.assertEqual(res["dropped_without_filed_date"], 1)

    def test_health_is_honest_about_configuration(self):
        self.assertEqual(EdgarClient().health()["status"], "NEEDS_CONTACT_EMAIL")
        h = EdgarClient(contact_email="me@example.com").health()
        self.assertEqual(h["status"], "READY")
        self.assertEqual(h["rate_limit"], "10 req/sec")
        self.assertIn("미검증", h["verified"])

    def test_stats_are_tracked(self):
        c = EdgarClient(contact_email="me@example.com",
                        transport=FakeTransport(SUBMISSIONS))
        c.fetch_filings("320193")
        self.assertEqual(c.stats.requests, 1)
        self.assertGreater(c.stats.bytes_received, 0)


if __name__ == "__main__":
    unittest.main()
