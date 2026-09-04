"""한국 데이터 수집기 검증 — 공공데이터포털 시세 + DART 공시.

★ 인터넷 없이 어떻게 검증하는가
   두 수집기 모두 `Transport` 를 주입받습니다. 실제 응답 형식을 그대로
   넣어 파싱·페이징·오류처리·PIT 규칙을 전부 검증합니다.
   남는 미검증 항목은 "서버에 실제로 닿는가" 하나뿐입니다.
"""

import json
import unittest
import zipfile
import io

from packages.market_data import DataGoKrProvider, MarketDataError
from packages.market_data.data_go_kr import _looks_url_encoded
from packages.dart import (
    DartClient,
    DartError,
    DartParseError,
    filings_as_pit_records,
    financials_as_pit_records,
    parse_filing_list,
    parse_financials,
)


# =====================================================================
#  공공데이터포털 — 실제 응답 형식 (구조 그대로, 값은 예시)
# =====================================================================
def _price_page(rows, total=None, code="00"):
    return json.dumps({
        "response": {
            "header": {"resultCode": code, "resultMsg": "NORMAL SERVICE."},
            "body": {
                "numOfRows": len(rows),
                "pageNo": 1,
                "totalCount": total if total is not None else len(rows),
                "items": {"item": rows},
            },
        }
    }, ensure_ascii=False).encode()


ROW1 = {"basDt": "20240102", "srtnCd": "005930", "isinCd": "KR7005930003",
        "itmsNm": "삼성전자", "mrktCtg": "KOSPI", "clpr": "79600",
        "vs": "1000", "fltRt": "1.27", "mkp": "78200", "hipr": "79800",
        "lopr": "78200", "trqu": "17142848", "trPrc": "1360000000000",
        "lstgStCnt": "5969782550", "mrktTotAmt": "475274491180000"}
ROW2 = {**ROW1, "basDt": "20240103", "clpr": "77000", "mkp": "78800",
        "hipr": "79000", "lopr": "76500", "trqu": "21753644"}

# 키가 틀렸을 때 — JSON 을 요청해도 XML 이 옵니다
XML_BAD_KEY = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<OpenAPI_ServiceResponse><cmmMsgHeader>'
    b'<errMsg>SERVICE ERROR</errMsg>'
    b'<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>'
    b'<returnReasonCode>30</returnReasonCode>'
    b'</cmmMsgHeader></OpenAPI_ServiceResponse>'
)
XML_QUOTA = XML_BAD_KEY.replace(
    b"SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
    b"LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = payloads if isinstance(payloads, list) else [payloads]
        self.calls: list[str] = []
        self._i = 0

    def get(self, url, headers=None, timeout=20.0):
        self.calls.append(url)
        p = self.payloads[min(self._i, len(self.payloads) - 1)]
        self._i += 1
        if isinstance(p, Exception):
            raise p
        return p


# =====================================================================
class TestServiceKeyEncoding(unittest.TestCase):
    """★ 이 API 최대의 함정 — 키 인코딩."""

    def test_detects_encoded_key(self):
        self.assertTrue(_looks_url_encoded("abc%2Bdef%3D%3D"))
        self.assertTrue(_looks_url_encoded("aB9%2FxY%3D"))

    def test_detects_decoded_key(self):
        self.assertFalse(_looks_url_encoded("abc+def=="))
        self.assertFalse(_looks_url_encoded("aB9/xY="))
        self.assertFalse(_looks_url_encoded("plainAlphaNumericKey123"))

    def test_decoded_key_gets_encoded_in_url(self):
        """★ `+` 를 그대로 두면 서버가 공백으로 읽어 키가 틀렸다고 합니다."""
        t = FakeTransport(_price_page([ROW1]))
        raw = "abcDEF012" * 6 + "+xy/z=="          # 실제 키와 비슷한 길이
        p = DataGoKrProvider(service_key=raw, transport=t, min_interval=0.0)
        p.fetch("005930")
        url = t.calls[0]
        self.assertIn("%2Bxy%2Fz%3D%3D", url)
        self.assertNotIn("+xy/z==", url)

    def test_encoded_key_is_left_alone(self):
        """이미 인코딩된 키를 또 인코딩하면 %가 %25 가 되어 깨집니다."""
        t = FakeTransport(_price_page([ROW1]))
        raw = "abcDEF012" * 6 + "%2Bxy%2Fz%3D%3D"   # 이미 인코딩된 키
        p = DataGoKrProvider(service_key=raw, transport=t, min_interval=0.0)
        p.fetch("005930")
        self.assertIn("%2Bxy%2Fz%3D%3D", t.calls[0])
        self.assertNotIn("%252B", t.calls[0], "이미 인코딩된 키를 또 인코딩했습니다")

    def test_missing_key_is_reported_before_any_request(self):
        t = FakeTransport(_price_page([ROW1]))
        p = DataGoKrProvider(service_key="", transport=t, min_interval=0.0)
        res = p.fetch("005930")
        self.assertFalse(res.ok)
        self.assertIn("DATA_GO_KR_KEY", res.error)
        self.assertEqual(t.calls, [], "키도 없이 요청을 보내면 안 됩니다")


class TestDataGoKrParsing(unittest.TestCase):
    def setUp(self):
        self.t = FakeTransport(_price_page([ROW1, ROW2]))
        self.p = DataGoKrProvider(service_key="k" * 30, transport=self.t,
                                  min_interval=0.0)

    def test_parses_rows(self):
        res = self.p.fetch("005930")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.bars), 2)

    def test_maps_korean_field_names_correctly(self):
        """mkp=시가, hipr=고가, lopr=저가, clpr=종가, trqu=거래량."""
        res = self.p.fetch("005930")
        b = res.bars.bars[0]
        self.assertEqual(b.open, 78200.0)
        self.assertEqual(b.high, 79800.0)
        self.assertEqual(b.low, 78200.0)
        self.assertEqual(b.close, 79600.0)
        self.assertEqual(b.volume, 17142848.0)

    def test_currency_is_krw(self):
        self.assertEqual(self.p.fetch("005930").bars.currency, "KRW")

    def test_marks_as_unadjusted(self):
        """★ 이 API 는 수정주가가 아닙니다. 안다고 말하면 안 됩니다."""
        res = self.p.fetch("005930")
        self.assertFalse(res.bars.adjusted)
        self.assertTrue(any("원주가" in n for n in res.bars.notes))

    def test_url_uses_krx_params(self):
        self.p.fetch("005930", start="2024-01-01", end="2024-12-31")
        url = self.t.calls[0]
        self.assertIn("likeSrtnCd=005930", url)
        self.assertIn("beginBasDt=20240101", url)
        self.assertIn("endBasDt=20241231", url)
        self.assertIn("resultType=json", url)
        self.assertTrue(url.startswith("https://"))

    def test_single_item_comes_as_object_not_list(self):
        """건수가 1이면 items.item 이 리스트가 아니라 객체로 옵니다."""
        payload = json.dumps({"response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"totalCount": 1, "items": {"item": ROW1}},
        }}, ensure_ascii=False).encode()
        p = DataGoKrProvider(service_key="k" * 30,
                             transport=FakeTransport(payload), min_interval=0.0)
        res = p.fetch("005930")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.bars), 1)

    def test_uses_xkrx_calendar(self):
        res = self.p.fetch("005930")
        self.assertTrue(res.quality.calendar_checked)
        self.assertEqual(res.quality.non_session_bars, 0)


class TestDataGoKrPaging(unittest.TestCase):
    def test_follows_pages_until_total(self):
        page1 = _price_page([ROW1], total=2)
        page2 = _price_page([ROW2], total=2)
        t = FakeTransport([page1, page2])
        p = DataGoKrProvider(service_key="k" * 30, transport=t,
                             min_interval=0.0)
        res = p.fetch("005930")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.bars), 2)
        self.assertEqual(len(t.calls), 2)
        self.assertIn("pageNo=2", t.calls[1])
        self.assertTrue(any("페이지" in n for n in res.bars.notes))

    def test_duplicate_dates_across_pages_are_merged(self):
        t = FakeTransport([_price_page([ROW1], total=3),
                           _price_page([ROW1], total=3)])
        p = DataGoKrProvider(service_key="k" * 30, transport=t,
                             min_interval=0.0)
        res = p.fetch("005930")
        self.assertEqual(len(res.bars), 1, "같은 날짜가 두 번 들어갔습니다")

    def test_page_limit_is_respected(self):
        t = FakeTransport(_price_page([ROW1], total=10_000))
        p = DataGoKrProvider(service_key="k" * 30, transport=t,
                             min_interval=0.0, max_pages=3)
        p.fetch("005930")
        self.assertEqual(len(t.calls), 3)


class TestDataGoKrErrors(unittest.TestCase):
    """★ 오류를 '알 수 없는 오류' 로 뭉개지 않는가."""

    def _err(self, payload):
        p = DataGoKrProvider(service_key="k" * 30,
                             transport=FakeTransport(payload), min_interval=0.0)
        return p.fetch("005930")

    def test_xml_bad_key_is_explained(self):
        res = self._err(XML_BAD_KEY)
        self.assertFalse(res.ok)
        self.assertIn("등록되지 않은 서비스 키", res.error)
        self.assertIn("활용신청", res.error)

    def test_xml_quota_is_explained(self):
        res = self._err(XML_QUOTA)
        self.assertFalse(res.ok)
        self.assertIn("한도", res.error)

    def test_result_code_no_data(self):
        res = self._err(_price_page([], code="03"))
        self.assertFalse(res.ok)
        self.assertIn("데이터가 없습니다", res.error)

    def test_result_code_is_translated(self):
        res = self._err(_price_page([], code="22"))
        self.assertFalse(res.ok)
        self.assertIn("요청 제한", res.error)

    def test_broken_json_shows_the_response(self):
        res = self._err(b"not json at all")
        self.assertFalse(res.ok)
        self.assertIn("not json", res.error)

    def test_empty_result_is_not_silently_ok(self):
        res = self._err(_price_page([], total=0))
        self.assertFalse(res.ok)
        self.assertIn("005930", res.error)

    def test_network_error_does_not_raise(self):
        res = self._err(MarketDataError("HTTP 500"))
        self.assertFalse(res.ok)
        self.assertIn("500", res.error)

    def test_health_is_honest(self):
        self.assertEqual(DataGoKrProvider().health()["status"], "NEEDS_KEY")
        h = DataGoKrProvider(service_key="k" * 30).health()
        self.assertEqual(h["status"], "READY")
        self.assertIn("미검증", h["verified"])
        self.assertEqual(h["cost"], "무료")


# =====================================================================
#  DART — 실제 응답 형식
# =====================================================================
FILING_LIST = json.dumps({
    "status": "000", "message": "정상",
    "page_no": 1, "page_count": 10, "total_count": 3, "total_page": 1,
    "list": [
        {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930",
         "corp_cls": "Y", "report_nm": "사업보고서 (2024.12)",
         "rcept_no": "20250311000123", "flr_nm": "삼성전자",
         "rcept_dt": "20250311", "rm": ""},
        {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930",
         "corp_cls": "Y", "report_nm": "분기보고서 (2024.09)",
         "rcept_no": "20241114000456", "flr_nm": "삼성전자",
         "rcept_dt": "20241114", "rm": ""},
        {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930",
         "corp_cls": "Y", "report_nm": "주요사항보고서(자기주식취득결정)",
         "rcept_no": "20241115000789", "flr_nm": "삼성전자",
         "rcept_dt": "20241115", "rm": "정"},
    ],
}, ensure_ascii=False).encode()

FILING_EMPTY = json.dumps(
    {"status": "013", "message": "조회된 데이타가 없습니다."},
    ensure_ascii=False).encode()
FILING_BAD_KEY = json.dumps(
    {"status": "010", "message": "등록되지 않은 키입니다."},
    ensure_ascii=False).encode()
FILING_QUOTA = json.dumps(
    {"status": "020", "message": "요청 제한을 초과하였습니다."},
    ensure_ascii=False).encode()

FINANCIALS = json.dumps({
    "status": "000", "message": "정상",
    "list": [
        {"rcept_no": "20250311000123", "bsns_year": "2024", "corp_code": "00126380",
         "fs_div": "CFS", "fs_nm": "연결재무제표", "sj_div": "IS", "sj_nm": "손익계산서",
         "account_nm": "매출액", "thstrm_nm": "제 56 기",
         "thstrm_amt": "300870903000000", "frmtrm_amt": "258935494000000",
         "bfefrmtrm_amt": "302231360000000", "reprt_code": "11011"},
        {"rcept_no": "20250311000123", "bsns_year": "2024", "corp_code": "00126380",
         "fs_div": "CFS", "fs_nm": "연결재무제표", "sj_div": "IS", "sj_nm": "손익계산서",
         "account_nm": "영업이익", "thstrm_nm": "제 56 기",
         "thstrm_amt": "32725961000000", "frmtrm_amt": "6566976000000",
         "bfefrmtrm_amt": "43376630000000", "reprt_code": "11011"},
        {"rcept_no": "20250311000123", "bsns_year": "2024", "corp_code": "00126380",
         "fs_div": "CFS", "sj_div": "BS", "account_nm": "자산총계",
         "thstrm_nm": "제 56 기", "thstrm_amt": "-", "reprt_code": "11011"},
    ],
}, ensure_ascii=False).encode()


def _corp_zip():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><result>'
        '<list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>'
        '<stock_code>005930</stock_code><modify_date>20240101</modify_date></list>'
        '<list><corp_code>00164779</corp_code><corp_name>SK하이닉스</corp_name>'
        '<stock_code>000660</stock_code><modify_date>20240101</modify_date></list>'
        '<list><corp_code>00999999</corp_code><corp_name>비상장회사</corp_name>'
        '<stock_code> </stock_code><modify_date>20240101</modify_date></list>'
        '</result>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", xml.encode("utf-8"))
    return buf.getvalue()


class TestDartKeyHandling(unittest.TestCase):
    def test_no_key_means_no_request(self):
        """★ 키 없이 남의 서버를 두드리지 않습니다."""
        t = FakeTransport(FILING_LIST)
        c = DartClient(api_key="", transport=t)
        res = c.fetch_filings(corp_code="00126380")
        self.assertFalse(res["ok"])
        self.assertIn("DART_API_KEY", res["error"])
        self.assertEqual(t.calls, [])

    def test_bad_key_format_is_caught_before_request(self):
        t = FakeTransport(FILING_LIST)
        c = DartClient(api_key="tooshort", transport=t)
        res = c.fetch_filings(corp_code="00126380")
        self.assertFalse(res["ok"])
        self.assertIn("40자리", res["error"])
        self.assertEqual(t.calls, [])

    def test_valid_key_is_accepted(self):
        self.assertTrue(DartClient(api_key="a1b2c3d4" * 5).configured)

    def test_key_is_sent_as_crtfc_key(self):
        t = FakeTransport(FILING_LIST)
        c = DartClient(api_key="a" * 40, transport=t)
        c.fetch_filings(corp_code="00126380")
        self.assertIn("crtfc_key=" + "a" * 40, t.calls[0])


class TestDartFilingList(unittest.TestCase):
    def setUp(self):
        self.c = DartClient(api_key="a" * 40, transport=FakeTransport(FILING_LIST))

    def test_parses_filings(self):
        res = self.c.fetch_filings(corp_code="00126380")
        self.assertTrue(res["ok"], res.get("error"))
        self.assertEqual(res["count"], 3)
        self.assertEqual(res["filings"][0]["corp_name"], "삼성전자")

    def test_rcept_dt_is_the_publication_date(self):
        """★ 사업보고서는 결산기말이 아니라 접수일에 공개됩니다."""
        res = self.c.fetch_filings(corp_code="00126380")
        annual = res["filings"][0]
        self.assertEqual(annual["rcept_dt"], "20250311")
        self.assertIn("2024.12", annual["report_nm"])   # 대상 기간은 2024년 말
        self.assertIn("rcept_dt", annual["pit_note"])

    def test_market_code_is_translated(self):
        res = self.c.fetch_filings(corp_code="00126380")
        self.assertEqual(res["filings"][0]["market"], "KOSPI")

    def test_url_points_to_the_original_document(self):
        res = self.c.fetch_filings(corp_code="00126380")
        url = res["filings"][0]["url"]
        self.assertTrue(url.startswith("https://dart.fss.or.kr/"))
        self.assertIn("20250311000123", url)

    def test_no_data_status_is_explained_not_crashed(self):
        c = DartClient(api_key="a" * 40, transport=FakeTransport(FILING_EMPTY))
        res = c.fetch_filings(corp_code="00126380")
        self.assertFalse(res["ok"])
        self.assertIn("조회된 데이터가 없습니다", res["error"])
        self.assertIn("넓혀보세요", res["error"])

    def test_bad_key_status_is_actionable(self):
        c = DartClient(api_key="a" * 40, transport=FakeTransport(FILING_BAD_KEY))
        res = c.fetch_filings(corp_code="00126380")
        self.assertIn("등록되지 않은 키", res["error"])
        self.assertIn("opendart.fss.or.kr", res["error"])

    def test_quota_status_is_actionable(self):
        c = DartClient(api_key="a" * 40, transport=FakeTransport(FILING_QUOTA))
        res = c.fetch_filings(corp_code="00126380")
        self.assertIn("20,000", res["error"])

    def test_dates_are_normalized(self):
        t = FakeTransport(FILING_LIST)
        c = DartClient(api_key="a" * 40, transport=t)
        c.fetch_filings(corp_code="00126380", begin="2024-01-01", end="2024-12-31")
        self.assertIn("bgn_de=20240101", t.calls[0])
        self.assertIn("end_de=20241231", t.calls[0])


class TestDartCorpCodes(unittest.TestCase):
    def test_loads_mapping_from_zip(self):
        c = DartClient(api_key="a" * 40)
        n = c.load_corp_codes(_corp_zip())
        self.assertEqual(n, 2, "상장사 2곳이어야 합니다 (비상장 제외)")
        self.assertEqual(c.corp_code_for("005930"), "00126380")
        self.assertEqual(c.corp_name_for("000660"), "SK하이닉스")

    def test_pads_short_codes(self):
        c = DartClient(api_key="a" * 40)
        c.load_corp_codes(_corp_zip())
        self.assertEqual(c.corp_code_for("660"), "00164779")

    def test_unknown_symbol_is_explained(self):
        c = DartClient(api_key="a" * 40)
        c.load_corp_codes(_corp_zip())
        with self.assertRaises(DartError) as ctx:
            c.corp_code_for("999999")
        self.assertIn("찾지 못했습니다", str(ctx.exception))

    def test_non_zip_response_is_explained(self):
        c = DartClient(api_key="a" * 40)
        with self.assertRaises(DartError) as ctx:
            c.load_corp_codes(FILING_BAD_KEY)
        self.assertIn("등록되지 않은 키", str(ctx.exception))

    def test_stock_code_resolves_automatically(self):
        t = FakeTransport([_corp_zip(), FILING_LIST])
        c = DartClient(api_key="a" * 40, transport=t)
        res = c.fetch_filings(stock_code="005930")
        self.assertTrue(res["ok"], res.get("error"))
        self.assertIn("corp_code=00126380", t.calls[1])


class TestDartFinancials(unittest.TestCase):
    def test_parses_amounts(self):
        items = parse_financials(FINANCIALS)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].account_nm, "매출액")
        self.assertEqual(items[0].thstrm_amt, 300870903000000.0)

    def test_dash_amount_becomes_none_not_zero(self):
        """★ '아직 모른다' 와 '값이 0이다' 는 다릅니다."""
        items = parse_financials(FINANCIALS)
        self.assertIsNone(items[2].thstrm_amt)

    def test_refuses_to_build_pit_records_without_filing_date(self):
        """★ 언제 알 수 있었는지 모르는 숫자는 백테스트에 쓸 수 없습니다."""
        items = parse_financials(FINANCIALS)
        with self.assertRaises(DartParseError) as ctx:
            financials_as_pit_records(items, "005930", rcept_dt="")
        self.assertIn("접수일자", str(ctx.exception))
        self.assertIn("미래", str(ctx.exception))

    def test_builds_pit_records_with_filing_date(self):
        items = parse_financials(FINANCIALS)
        recs = financials_as_pit_records(items, "005930", rcept_dt="20250311")
        self.assertEqual(len(recs), 2)      # '-' 인 항목은 제외
        for r in recs:
            self.assertEqual(r["published_time"], r["event_time"])

    def test_api_warns_when_filing_date_is_missing(self):
        t = FakeTransport([_corp_zip(), FINANCIALS])
        c = DartClient(api_key="a" * 40, transport=t)
        res = c.fetch_financials("005930", "2024")
        self.assertTrue(res["ok"])
        self.assertIn("pit_warning", res)
        self.assertIn("미래 정보", res["pit_warning"])
        self.assertNotIn("pit_records", res)

    def test_api_builds_pit_records_when_given_the_date(self):
        t = FakeTransport([_corp_zip(), FINANCIALS])
        c = DartClient(api_key="a" * 40, transport=t)
        res = c.fetch_financials("005930", "2024", rcept_dt="20250311")
        self.assertEqual(res["pit_records"], 2)
        self.assertEqual(res["published_date"], "20250311")


class TestDartPitIntegration(unittest.TestCase):
    def test_annual_report_is_invisible_before_the_filing_date(self):
        """★ 2024년 실적은 2025-03-11 이전에는 볼 수 없어야 합니다."""
        from packages.pit_store.store import PITStore, Record

        items = parse_financials(FINANCIALS)
        pit = PITStore()
        for r in financials_as_pit_records(items, "005930", "20250311"):
            pit.put_fact(Record(key=r["key"], value=r["value"],
                                event_time=r["event_time"],
                                published_time=r["published_time"],
                                source_id=r["source_id"]))
        key = "005930:CFS:매출액:2024:11011"
        year_end = 1735603200        # 2024-12-31
        filed = 1741651200           # 2025-03-11

        self.assertIsNone(pit.get_fact(key, year_end),
                          "결산기말에 이미 매출을 알면 미래를 보는 것입니다")
        rec = pit.get_fact(key, filed + 86400)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.value, 300870903000000.0)

    def test_filing_list_records_use_rcept_dt(self):
        _, filings = parse_filing_list(FILING_LIST)
        recs = filings_as_pit_records(filings)
        self.assertEqual(len(recs), 3)
        for r in recs:
            self.assertEqual(r["published_time"], r["event_time"])

    def test_health_is_honest(self):
        self.assertEqual(DartClient().health()["status"], "NEEDS_KEY")
        h = DartClient(api_key="a" * 40).health()
        self.assertEqual(h["status"], "READY")
        self.assertEqual(h["cost"], "무료")
        self.assertIn("20,000", h["rate_limit"])
        self.assertIn("미검증", h["verified"])


if __name__ == "__main__":
    unittest.main()
