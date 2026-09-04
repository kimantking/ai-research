"""실제 시장 데이터 공급자 검증 (Phase 21).

★ 어떻게 인터넷 없이 검증하는가

   네트워크 호출을 `Transport` 뒤로 빼두었기 때문에, 실제 응답 형식을
   그대로 넣어 파싱·정규화·품질검사를 **전부** 검증할 수 있습니다.

   검증되지 않은 채 남는 것은 "실제로 서버에 닿는가" 하나뿐이고,
   그 사실은 공급자의 `verified` 필드에 정직하게 적혀 있습니다.
"""

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile

from packages.market_data import (
    Bars,
    CsvFileProvider,
    MarketDataError,
    StooqProvider,
    YFinanceProvider,
    ingest_bars,
    to_ohlcv,
)
from packages.market_data.base import Bar, UrlTransport, check_quality
from packages.market_data.ingest import publish_time_for


# ---- 실제 Stooq 응답 형식 (형식 그대로, 값은 예시) ----
STOOQ_CSV = b"""Date,Open,High,Low,Close,Volume
2024-01-02,187.15,188.44,183.89,185.64,82488700
2024-01-03,184.22,185.88,183.43,184.25,58414500
2024-01-04,182.15,183.09,180.88,181.91,71983600
2024-01-05,181.99,182.76,180.17,181.18,62303300
2024-01-08,182.09,185.60,181.50,185.56,59144500
"""

STOOQ_NO_DATA = b"No data\n"


class FakeTransport:
    """저장해 둔 응답을 돌려주는 가짜 전송 계층."""

    def __init__(self, payload: bytes | Exception):
        self.payload = payload
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=20.0):
        self.calls.append(url)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


# ====================================================================== Stooq
class TestStooqParsing(unittest.TestCase):
    def setUp(self):
        self.t = FakeTransport(STOOQ_CSV)
        self.p = StooqProvider(transport=self.t, min_interval=0.0)

    def test_parses_all_rows(self):
        res = self.p.fetch("AAPL")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.bars), 5)
        self.assertEqual(res.bars.symbol, "AAPL")

    def test_values_are_exact(self):
        res = self.p.fetch("AAPL")
        first = res.bars.bars[0]
        self.assertEqual(first.open, 187.15)
        self.assertEqual(first.high, 188.44)
        self.assertEqual(first.low, 183.89)
        self.assertEqual(first.close, 185.64)
        self.assertEqual(first.volume, 82488700.0)

    def test_timestamp_is_utc_midnight_of_that_date(self):
        res = self.p.fetch("AAPL")
        ts = res.bars.bars[0].ts
        d = datetime.fromtimestamp(ts, tz=timezone.utc)
        self.assertEqual((d.year, d.month, d.day), (2024, 1, 2))
        self.assertEqual((d.hour, d.minute, d.second), (0, 0, 0))

    def test_bars_are_sorted(self):
        res = self.p.fetch("AAPL")
        ts = [b.ts for b in res.bars]
        self.assertEqual(ts, sorted(ts))

    def test_never_claims_adjusted(self):
        """★ 조정 여부를 모르면 안다고 하면 안 됩니다."""
        res = self.p.fetch("AAPL")
        self.assertFalse(res.bars.adjusted)
        self.assertTrue(any("adjusted=False" in n for n in res.bars.notes))

    def test_url_shape(self):
        self.p.fetch("AAPL", start="2024-01-01", end="2024-01-31")
        url = self.t.calls[0]
        self.assertIn("s=aapl.us", url)
        self.assertIn("i=d", url)
        self.assertIn("d1=20240101", url)
        self.assertIn("d2=20240131", url)
        self.assertTrue(url.startswith("https://"))

    def test_korean_symbol_gets_kr_suffix(self):
        self.p.fetch("005930")
        self.assertIn("s=005930.kr", self.t.calls[0])

    def test_explicit_suffix_is_respected(self):
        self.p.fetch("bmw.de")
        self.assertIn("s=bmw.de", self.t.calls[0])

    def test_no_data_response_is_an_error_not_empty_bars(self):
        """★ 조용히 빈 결과를 주면 사용자가 눈치채지 못합니다."""
        p = StooqProvider(transport=FakeTransport(STOOQ_NO_DATA), min_interval=0.0)
        res = p.fetch("NOSUCH")
        self.assertFalse(res.ok)
        self.assertIn("데이터가 없습니다", res.error)

    def test_unexpected_header_is_reported_clearly(self):
        bad = b"Datum,Eroeffnung,Hoch\n2024-01-02,1,2\n"
        p = StooqProvider(transport=FakeTransport(bad), min_interval=0.0)
        res = p.fetch("AAPL")
        self.assertFalse(res.ok)
        self.assertIn("CSV 형식이 예상과 다릅니다", res.error)

    def test_network_failure_does_not_raise(self):
        p = StooqProvider(
            transport=FakeTransport(MarketDataError("HTTP 503")), min_interval=0.0)
        res = p.fetch("AAPL")
        self.assertFalse(res.ok)
        self.assertIn("503", res.error)

    def test_broken_rows_are_skipped_and_counted(self):
        raw = STOOQ_CSV + b"2024-01-09,bad,rows,here,nope\n"
        p = StooqProvider(transport=FakeTransport(raw), min_interval=0.0)
        res = p.fetch("AAPL")
        self.assertTrue(res.ok)
        self.assertEqual(len(res.bars), 5)
        self.assertTrue(any("건너뛰" in n for n in res.bars.notes))

    def test_health_declares_it_is_unverified(self):
        h = self.p.health()
        self.assertFalse(h["requires_key"])
        self.assertIn("미검증", h["verified"])


class TestUrlTransportSafety(unittest.TestCase):
    def test_refuses_plain_http(self):
        t = UrlTransport()
        with self.assertRaises(MarketDataError) as ctx:
            t.get("http://example.com/data.csv")
        self.assertIn("HTTPS", str(ctx.exception))


# ====================================================================== CSV
class TestCsvFileProvider(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.p = CsvFileProvider(directory=self.dir)

    def _write(self, name: str, text: str):
        (self.dir / name).write_text(text, encoding="utf-8")

    def test_standard_format(self):
        self._write("NVDA.csv",
                    "Date,Open,High,Low,Close,Volume\n"
                    "2024-03-01,100,105,99,104,1000\n"
                    "2024-03-04,104,108,103,107,1200\n")
        res = self.p.fetch("NVDA")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.bars), 2)
        self.assertEqual(res.bars.bars[1].close, 107.0)

    def test_korean_headers(self):
        self._write("SK.csv",
                    "일자,시가,고가,저가,종가,거래량\n"
                    "2024/03/01,100,105,99,104,1000\n")
        res = self.p.fetch("SK")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.bars.bars[0].open, 100.0)

    def test_compact_date_and_thousands_separator(self):
        self._write("X.csv",
                    "date,open,high,low,close,volume\n"
                    '20240301,"1,000","1,050",990,"1,040","12,345"\n')
        res = self.p.fetch("X")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.bars.bars[0].open, 1000.0)
        self.assertEqual(res.bars.bars[0].volume, 12345.0)

    def test_missing_volume_defaults_to_zero(self):
        self._write("Y.csv", "date,open,high,low,close\n2024-03-01,1,2,0.5,1.5\n")
        res = self.p.fetch("Y")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.bars.bars[0].volume, 0.0)

    def test_missing_file_says_where_to_put_it(self):
        res = self.p.fetch("NOPE")
        self.assertFalse(res.ok)
        self.assertIn("넣어주세요", res.error)

    def test_missing_columns_shows_the_header(self):
        self._write("Z.csv", "foo,bar\n1,2\n")
        res = self.p.fetch("Z")
        self.assertFalse(res.ok)
        self.assertIn("필요한 컬럼", res.error)
        self.assertIn("foo,bar", res.error)

    def test_date_range_filter(self):
        self._write("R.csv",
                    "date,open,high,low,close\n"
                    "2024-01-02,1,2,0.5,1.5\n"
                    "2024-02-02,1,2,0.5,1.5\n"
                    "2024-03-02,1,2,0.5,1.5\n")
        res = self.p.fetch("R", start="2024-02-01", end="2024-02-28")
        self.assertEqual(len(res.bars), 1)

    def test_health_lists_available_symbols(self):
        self._write("AAA.csv", "date,open,high,low,close\n2024-01-02,1,2,0.5,1.5\n")
        h = self.p.health()
        self.assertEqual(h["symbols_found"], ["AAA"])
        self.assertEqual(h["status"], "CONNECTED")

    def test_empty_directory_is_not_an_error(self):
        h = CsvFileProvider(directory=self.dir / "nope").health()
        self.assertEqual(h["status"], "EMPTY")


# ====================================================================== 품질검사
class TestQualityChecks(unittest.TestCase):
    def _bars(self, rows):
        return Bars(symbol="T", bars=[Bar(*r) for r in rows], source="test")

    def test_clean_data_is_usable(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([
            (base, 10, 11, 9, 10.5, 100),
            (base + 86400, 10.5, 11.5, 10, 11, 120),
        ]))
        self.assertTrue(rep.usable)
        self.assertEqual(rep.problems, [])

    def test_detects_high_below_low(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([(base, 10, 8, 12, 10, 100)]))
        self.assertEqual(rep.inconsistent_ohlc, 1)
        self.assertFalse(rep.usable)

    def test_detects_close_outside_range(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([(base, 10, 11, 9, 15, 100)]))
        self.assertEqual(rep.inconsistent_ohlc, 1)

    def test_detects_duplicates(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([
            (base, 10, 11, 9, 10, 100),
            (base, 10, 11, 9, 10, 100),
        ]))
        self.assertEqual(rep.duplicates, 1)
        self.assertFalse(rep.usable)

    def test_detects_out_of_order(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([
            (base + 86400, 10, 11, 9, 10, 100),
            (base, 10, 11, 9, 10, 100),
        ]))
        self.assertEqual(rep.out_of_order, 1)

    def test_detects_unadjusted_split(self):
        """★ 2:1 분할이 반영 안 되면 하루에 -50% 로 보입니다."""
        base = 1_700_000_000
        rep = check_quality(self._bars([
            (base, 200, 201, 199, 200, 100),
            (base + 86400, 100, 101, 99, 100, 200),
        ]))
        self.assertEqual(len(rep.extreme_moves), 1)
        self.assertTrue(any("분할" in p for p in rep.problems))
        # 치명적 오류는 아니므로 usable 은 유지 — 경고일 뿐입니다.
        self.assertTrue(rep.usable)

    def test_detects_non_positive_price(self):
        base = 1_700_000_000
        rep = check_quality(self._bars([(base, 0, 1, 0, 0.5, 10)]))
        self.assertEqual(rep.non_positive_prices, 1)
        self.assertFalse(rep.usable)

    def test_calendar_check_finds_weekend_bars(self):
        from packages.market_calendar import NYSE
        rows = [(NYSE.to_ts(date(2024, 3, d)), 10, 11, 9, 10, 100)
                for d in range(1, 15)]        # 주말 포함
        rep = check_quality(self._bars(rows), exchange="XNYS")
        self.assertTrue(rep.calendar_checked)
        self.assertGreater(rep.non_session_bars, 0)

    def test_calendar_check_passes_for_real_sessions(self):
        from packages.market_calendar import NYSE, get_calendar
        days = get_calendar("XNYS").sessions_between(date(2024, 3, 1), date(2024, 3, 28))
        rows = [(NYSE.to_ts(d), 10, 11, 9, 10, 100) for d in days]
        rep = check_quality(self._bars(rows), exchange="XNYS")
        self.assertEqual(rep.non_session_bars, 0)
        self.assertEqual(rep.gaps, 0)


# ====================================================================== 적재
class TestIngest(unittest.TestCase):
    def setUp(self):
        self.p = StooqProvider(transport=FakeTransport(STOOQ_CSV), min_interval=0.0)
        self.bars = self.p.fetch("AAPL").bars

    def test_publish_time_is_after_the_close(self):
        """★ 그날 아침에 그날 종가를 알 수는 없습니다."""
        ts = self.bars.bars[0].ts
        pub = publish_time_for(ts, "XNYS")
        self.assertGreater(pub, ts)
        self.assertGreaterEqual(pub - ts, 20 * 3600)

    def test_unknown_exchange_is_most_conservative(self):
        ts = self.bars.bars[0].ts
        self.assertGreater(publish_time_for(ts, None),
                           publish_time_for(ts, "XNYS"))

    def test_pit_store_hides_the_close_before_the_close(self):
        from packages.pit_store.store import PITStore
        pit = PITStore()
        ingest_bars(self.bars, pit_store=pit, exchange="XNYS")
        ts = self.bars.bars[0].ts
        # 그날 아침에는 보이지 않습니다
        self.assertIsNone(pit.get_fact("AAPL:close", ts + 3600))
        # 마감 이후에는 보입니다
        rec = pit.get_fact("AAPL:close", ts + 22 * 3600)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.value, 185.64)

    def test_stores_bars_in_sqlite(self):
        from packages.persistence import SqliteStore
        store = SqliteStore(":memory:")
        rep = ingest_bars(self.bars, store=store, exchange="XNYS")
        self.assertEqual(rep["stored_bars"], 5)
        self.assertEqual(len(store.get_bars("AAPL")), 5)
        self.assertEqual(store.symbols(), ["AAPL"])
        store.close()

    def test_reingest_is_idempotent(self):
        from packages.persistence import SqliteStore
        store = SqliteStore(":memory:")
        ingest_bars(self.bars, store=store)
        ingest_bars(self.bars, store=store)
        self.assertEqual(len(store.get_bars("AAPL")), 5)
        store.close()

    def test_to_ohlcv_conversion(self):
        series = to_ohlcv(self.bars)
        self.assertEqual(len(series), 5)
        self.assertEqual(series.closes[0], 185.64)

    def test_ingest_reports_errors_without_raising(self):
        class BrokenStore:
            def put_bars(self, *a, **k):
                raise RuntimeError("디스크 가득")
        rep = ingest_bars(self.bars, store=BrokenStore())
        self.assertEqual(rep["stored_bars"], 0)
        self.assertTrue(rep["errors"])


# ====================================================================== yfinance
class TestYFinanceProvider(unittest.TestCase):
    def test_missing_package_is_not_an_error(self):
        p = YFinanceProvider()
        if p.is_installed():
            self.skipTest("이 환경에는 yfinance 가 설치되어 있습니다")
        res = p.fetch("AAPL")
        self.assertFalse(res.ok)
        self.assertIn("오류가 아닙니다", res.error)

    def test_health_reports_not_installed_honestly(self):
        h = YFinanceProvider().health()
        self.assertIn(h["status"], ("CONNECTED", "NOT_INSTALLED"))
        self.assertIn("재배포", h["terms_note"])

    def test_defaults_to_raw_prices_not_adjusted(self):
        """★ 조정주가는 과거 값이 나중에 바뀌어 PIT 원칙과 충돌합니다."""
        self.assertFalse(YFinanceProvider().auto_adjust)


if __name__ == "__main__":
    unittest.main()


class TestRestartContinuity(unittest.TestCase):
    """★ 재시작해도 실데이터와 학습이 이어지는가 (Phase 5b + 21 결합).

    이 두 기능은 따로 테스트해서는 잡히지 않는 실수가 있습니다.
    실제로 겪은 것: 저장소에 캔들이 남아 있는데도 재시작 직후
    화면이 MOCK 으로 표시되던 문제.
    """

    @classmethod
    def setUpClass(cls):
        import shutil
        from datetime import date

        from packages.market_calendar import get_calendar

        cls.tmp = Path(tempfile.mkdtemp())
        cls.mkt = cls.tmp / "market"
        cls.mkt.mkdir()
        cls.db = cls.tmp / "t.db"

        days = get_calendar("XNYS").sessions_between(date(2023, 1, 3), date(2024, 12, 31))
        rows = ["Date,Open,High,Low,Close,Volume"]
        px = 100.0
        for i, d in enumerate(days):
            o = px
            c = o * (1.004 if i % 3 else 0.997)
            rows.append(f"{d.isoformat()},{o:.2f},{max(o,c)*1.01:.2f},"
                        f"{min(o,c)*0.99:.2f},{c:.2f},1000000")
            px = c
        (cls.mkt / "ZZTEST.csv").write_text("\n".join(rows), encoding="utf-8")

    def test_real_data_and_learning_survive_a_restart(self):
        from services.agent_runtime.engine import Engine

        eng = Engine(config_dir=Path("config"), db_path=self.db)
        res = eng.load_market_data(provider="csv_file",
                                   data_dir=str(self.mkt), exchange="XNYS")
        self.assertTrue(res["ok"], res.get("error"))
        for _ in range(120):
            eng.tick()
        weights = list(eng.states["technical_master"].model.weights)
        samples = sum(s.model.samples_seen for s in eng.states.values())
        self.assertGreater(samples, 0)
        eng.close()

        again = Engine(config_dir=Path("config"), db_path=self.db)
        try:
            self.assertTrue(again.restore_report["restored"])
            self.assertEqual(
                list(again.states["technical_master"].model.weights), weights,
                "모델 가중치가 복구되지 않았습니다 — 학습이 사라진 것입니다")
            self.assertEqual(
                sum(s.model.samples_seen for s in again.states.values()), samples)
            # ★ 재시작 직후부터 실데이터를 인식해야 합니다
            self.assertIn("ZZTEST", again.real_symbols)
            self.assertNotEqual(again.data_mode(), "MOCK",
                                "DB 에 실제 캔들이 있는데 MOCK 이라고 표시합니다")
            self.assertEqual(
                [s["symbol"] for s in again.market_status()["symbols"]], ["ZZTEST"])
        finally:
            again.close()

    def test_learning_continues_from_where_it_stopped(self):
        from services.agent_runtime.engine import Engine

        db = self.tmp / "t2.db"
        eng = Engine(config_dir=Path("config"), db_path=db)
        for _ in range(100):
            eng.tick()
        before = sum(s.model.samples_seen for s in eng.states.values())
        eng.close()

        again = Engine(config_dir=Path("config"), db_path=db)
        try:
            for _ in range(100):
                again.tick()
            after = sum(s.model.samples_seen for s in again.states.values())
            self.assertGreater(after, before,
                               "재시작 후 학습이 이어지지 않고 처음부터 시작했습니다")
        finally:
            again.close()

    def test_memory_only_mode_still_works(self):
        """★ 영속화가 꺼져 있어도 시스템은 정상 동작해야 합니다."""
        from services.agent_runtime.engine import Engine

        eng = Engine(config_dir=Path("config"))      # db_path 없음
        for _ in range(30):
            eng.tick()
        st = eng.persistence_status()
        self.assertFalse(st["enabled"])
        self.assertIn("사라집니다", st["warning"])
        self.assertEqual(eng.data_mode(), "MOCK")

    def test_broken_store_path_does_not_crash_startup(self):
        """★ 'DB 때문에 프로그램이 안 켜진다' 는 최악입니다."""
        from services.agent_runtime.engine import Engine

        bad = self.tmp / "nope" / "\x00bad.db"
        eng = Engine(config_dir=Path("config"), db_path=bad)
        eng.tick()
        self.assertIsNone(eng.store)
        self.assertFalse(eng.persistence_status()["enabled"])


class TestResetLearningKeepsMarketData(unittest.TestCase):
    """★ 합성 학습만 지우고 실제 시세는 남기는가.

    실데이터로 넘어갈 때 필요한 동작입니다. 합성 캔들 생성기에는
    의도적인 사이클이 들어 있어서, 그 위에서 배운 가중치를 그대로 두면
    에이전트가 '없는 규칙' 을 이미 믿는 상태로 실전을 시작합니다.
    """

    def test_clears_learning_but_keeps_bars_and_facts(self):
        from packages.persistence import SqliteStore

        store = SqliteStore(":memory:")
        store.put_kv("agent_state", "tech", {"weights": [1.0, 2.0]})
        store.append_event("agent.step", {"detail": "x"})
        store.upsert_prediction({"pred_id": "p1", "agent_id": "tech"})
        store.put_bars("NVDA", [{"ts": 1_700_000_000, "o": 1, "h": 2,
                                 "l": 0.5, "c": 1.5, "v": 10}])
        store.put_fact("NVDA:close", 1.5, published_time=1_700_086_400,
                       event_time=1_700_000_000)

        result = store.reset_learning()
        rows = store.stats()["rows"]

        self.assertEqual(rows["kv"], 0)
        self.assertEqual(rows["predictions"], 0)
        self.assertEqual(rows["events"], 0)
        # ★ 시세와 PIT 사실은 '배운 것' 이 아니라 '받아온 사실' 입니다
        self.assertEqual(rows["bars"], 1, "실제 시세가 지워졌습니다")
        self.assertEqual(rows["facts"], 1, "PIT 사실이 지워졌습니다")
        self.assertEqual(result["kept"]["bars"], 1)
        store.close()

    def test_engine_restarts_clean_but_still_sees_real_data(self):
        from packages.persistence import SqliteStore
        from services.agent_runtime.engine import Engine

        tmp = Path(tempfile.mkdtemp())
        mkt = tmp / "market"
        mkt.mkdir()
        (mkt / "QQTEST.csv").write_text(
            "Date,Open,High,Low,Close,Volume\n"
            + "\n".join(
                f"2024-0{1 + i // 20}-{1 + i % 20:02d},100,101,99,100.5,1000"
                for i in range(60)
            ),
            encoding="utf-8",
        )
        db = tmp / "r.db"

        eng = Engine(config_dir=Path("config"), db_path=db)
        eng.load_market_data(provider="csv_file", data_dir=str(mkt),
                             exchange="XNYS")
        for _ in range(80):
            eng.tick()
        self.assertGreater(sum(s.model.samples_seen for s in eng.states.values()), 0)
        eng.close()

        store = SqliteStore(db)
        store.reset_learning()
        store.close()

        fresh = Engine(config_dir=Path("config"), db_path=db)
        try:
            self.assertEqual(
                sum(s.model.samples_seen for s in fresh.states.values()), 0,
                "학습이 초기화되지 않았습니다")
            self.assertIn("QQTEST", fresh.real_symbols,
                          "실제 시세까지 함께 지워졌습니다")
        finally:
            fresh.close()
