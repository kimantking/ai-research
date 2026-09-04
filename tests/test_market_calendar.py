"""거래일 캘린더 검증.

★ 확인 방식
   외부 라이브러리가 없으므로, **공개된 실제 휴장일**을 직접 적어 놓고
   계산 결과가 그것과 일치하는지 봅니다.
   "코드가 스스로를 확인" 하는 게 아니라 "바깥 사실과 대조" 합니다.
"""

from datetime import date

import unittest

from packages.market_calendar import (
    CalendarError,
    KRX,
    NYSE,
    SessionClock,
    get_calendar,
    list_calendars,
)


class TestNYSEHolidays(unittest.TestCase):
    def setUp(self):
        self.cal = get_calendar("XNYS")

    def test_known_2024_holidays(self):
        # 2024년 NYSE 공식 휴장일
        expected = [
            date(2024, 1, 1),    # 신정
            date(2024, 1, 15),   # MLK
            date(2024, 2, 19),   # 워싱턴 탄생일
            date(2024, 3, 29),   # 성금요일
            date(2024, 5, 27),   # 메모리얼 데이
            date(2024, 6, 19),   # 준틴스
            date(2024, 7, 4),    # 독립기념일
            date(2024, 9, 2),    # 노동절
            date(2024, 11, 28),  # 추수감사절
            date(2024, 12, 25),  # 성탄절
        ]
        for d in expected:
            self.assertTrue(self.cal.is_holiday(d), f"{d} 가 휴장일로 인식되지 않음")
            self.assertFalse(self.cal.is_session(d))

    def test_known_2025_holidays(self):
        expected = [
            date(2025, 1, 1), date(2025, 1, 9),    # 카터 전 대통령 장례
            date(2025, 1, 20), date(2025, 2, 17),
            date(2025, 4, 18),                      # 성금요일
            date(2025, 5, 26), date(2025, 6, 19),
            date(2025, 7, 4), date(2025, 9, 1),
            date(2025, 11, 27), date(2025, 12, 25),
        ]
        for d in expected:
            self.assertTrue(self.cal.is_holiday(d), f"{d} 누락")

    def test_2026_holidays(self):
        for d in [date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
                  date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
                  date(2026, 7, 3),      # 7/4 가 토요일 → 7/3 금요일 관측
                  date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25)]:
            self.assertTrue(self.cal.is_holiday(d), f"{d} 누락")

    def test_ordinary_days_are_sessions(self):
        for d in [date(2024, 3, 5), date(2025, 8, 12), date(2026, 4, 15)]:
            self.assertTrue(self.cal.is_session(d), f"{d} 가 휴장으로 잘못 인식됨")

    def test_weekend_is_not_a_session(self):
        self.assertFalse(self.cal.is_session(date(2026, 9, 5)))   # 토
        self.assertFalse(self.cal.is_session(date(2026, 9, 6)))   # 일

    def test_special_closure_hurricane_sandy(self):
        self.assertTrue(self.cal.is_holiday(date(2012, 10, 29)))
        self.assertTrue(self.cal.is_holiday(date(2012, 10, 30)))
        self.assertTrue(self.cal.is_session(date(2012, 10, 31)))

    def test_juneteenth_did_not_exist_before_2022(self):
        self.assertFalse(self.cal.is_holiday(date(2021, 6, 18)))
        self.assertTrue(self.cal.is_holiday(date(2022, 6, 20)))   # 6/19 일 → 6/20 관측

    def test_mlk_did_not_exist_before_1998(self):
        self.assertFalse(self.cal.is_holiday(date(1997, 1, 20)))
        self.assertTrue(self.cal.is_holiday(date(1998, 1, 19)))


class TestNYSEEarlyClose(unittest.TestCase):
    def setUp(self):
        self.cal = get_calendar("NYSE")

    def test_day_after_thanksgiving(self):
        self.assertTrue(self.cal.is_early_close(date(2024, 11, 29)))
        self.assertIn("추수감사절", self.cal.early_close_reason(date(2024, 11, 29)))

    def test_christmas_eve_on_weekday(self):
        self.assertTrue(self.cal.is_early_close(date(2024, 12, 24)))

    def test_christmas_eve_on_weekend_is_not_early_close(self):
        # 2022-12-24 는 토요일
        self.assertFalse(self.cal.is_early_close(date(2022, 12, 24)))

    def test_holiday_is_not_early_close(self):
        self.assertFalse(self.cal.is_early_close(date(2024, 12, 25)))


class TestSessionNavigation(unittest.TestCase):
    def setUp(self):
        self.cal = get_calendar("XNYS")

    def test_friday_next_session_skips_weekend_and_labor_day(self):
        # 2026-09-04(금) → 09-07 은 노동절 → 다음 거래일은 09-08(화)
        self.assertEqual(self.cal.next_session(date(2026, 9, 4)),
                         date(2026, 9, 8))

    def test_next_session_skips_holiday(self):
        # 2024-12-24(화) 다음 거래일은 12-26(목). 12-25 는 성탄절 휴장.
        self.assertEqual(self.cal.next_session(date(2024, 12, 24)),
                         date(2024, 12, 26))

    def test_previous_session_skips_holiday(self):
        self.assertEqual(self.cal.previous_session(date(2024, 12, 26)),
                         date(2024, 12, 24))

    def test_next_session_n_steps(self):
        d = date(2024, 12, 20)          # 금
        self.assertEqual(self.cal.next_session(d, 1), date(2024, 12, 23))
        self.assertEqual(self.cal.next_session(d, 2), date(2024, 12, 24))
        self.assertEqual(self.cal.next_session(d, 3), date(2024, 12, 26))

    def test_sessions_between_counts_correctly(self):
        # 2024년 7월 1~7일: 1,2,3,5 는 거래일 / 4 독립기념일 / 6,7 주말
        got = self.cal.sessions_between(date(2024, 7, 1), date(2024, 7, 7))
        self.assertEqual([d.day for d in got], [1, 2, 3, 5])

    def test_2024_has_252_sessions(self):
        n = self.cal.session_count(date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(n, 252, f"2024년 거래일이 252일이 아닙니다: {n}")

    def test_2025_has_250_sessions(self):
        # 2025 는 카터 전 대통령 장례(1/9) 때문에 250일입니다.
        n = self.cal.session_count(date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(n, 250, f"2025년 거래일이 250일이 아닙니다: {n}")

    def test_align_pushes_off_holiday(self):
        self.assertEqual(self.cal.align(date(2024, 12, 25)), date(2024, 12, 26))
        self.assertEqual(self.cal.align(date(2024, 12, 25), "backward"),
                         date(2024, 12, 24))

    def test_n_must_be_positive(self):
        with self.assertRaises(CalendarError):
            self.cal.next_session(date(2024, 5, 1), 0)


class TestKRX(unittest.TestCase):
    def setUp(self):
        self.cal = get_calendar("KRX")

    def test_fixed_holidays(self):
        for d in [date(2025, 1, 1), date(2025, 3, 1), date(2025, 5, 5),
                  date(2025, 6, 6), date(2025, 8, 15), date(2025, 10, 3),
                  date(2025, 10, 9), date(2025, 12, 25)]:
            self.assertTrue(self.cal.is_holiday(d), f"{d} 누락")

    def test_lunar_new_year_2025(self):
        for d in [date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30)]:
            self.assertTrue(self.cal.is_holiday(d), f"설 연휴 {d} 누락")

    def test_chuseok_2024(self):
        for d in [date(2024, 9, 16), date(2024, 9, 17), date(2024, 9, 18)]:
            self.assertTrue(self.cal.is_holiday(d), f"추석 연휴 {d} 누락")

    def test_year_end_closing_day(self):
        self.assertTrue(self.cal.is_holiday(date(2025, 12, 31)))

    def test_refuses_to_guess_outside_lunar_table(self):
        """★ 모르면 모른다고 해야 합니다. 추측하면 조용히 틀립니다."""
        with self.assertRaises(CalendarError):
            self.cal.is_session(date(2040, 3, 2))
        with self.assertRaises(CalendarError):
            self.cal.is_session(date(2010, 3, 2))

    def test_coverage_declares_its_own_limits(self):
        cov = self.cal.coverage()
        self.assertEqual(cov["known_from"], 2015)
        self.assertEqual(cov["known_to"], 2035)
        self.assertTrue(any("음력" in c for c in cov["caveats"]))


class TestRegistry(unittest.TestCase):
    def test_aliases_resolve(self):
        for alias in ("NYSE", "nasdaq", "XNYS", "us"):
            self.assertEqual(get_calendar(alias).name, "XNYS")
        for alias in ("KRX", "kospi", "KOSDAQ", "kr"):
            self.assertEqual(get_calendar(alias).name, "XKRX")

    def test_unknown_exchange_raises(self):
        with self.assertRaises(CalendarError):
            get_calendar("XTOK")

    def test_list_calendars(self):
        self.assertEqual(sorted(list_calendars()), ["XKRX", "XNYS"])

    def test_same_object_is_reused(self):
        self.assertIs(get_calendar("NYSE"), get_calendar("XNYS"))


class TestSessionClock(unittest.TestCase):
    def test_detects_synthetic_series_is_not_aligned(self):
        """★ 합성 데이터는 주말에도 봉이 있습니다. 그걸 알아채야 합니다."""
        start = NYSE.to_ts(date(2024, 1, 1))
        ts = [start + i * 86_400 for i in range(30)]     # 달력일 연속
        clock = SessionClock.from_timestamps(ts, "XNYS")
        self.assertFalse(clock.is_aligned())
        self.assertGreater(len(clock.non_session_days()), 5)
        self.assertIn("정렬되지 않았습니다", clock.summary()["note"])

    def test_real_sessions_are_aligned(self):
        cal = get_calendar("XNYS")
        days = cal.sessions_between(date(2024, 3, 1), date(2024, 4, 30))
        ts = [NYSE.to_ts(d) for d in days]
        clock = SessionClock.from_timestamps(ts, "XNYS")
        self.assertTrue(clock.is_aligned())
        self.assertEqual(clock.missing_sessions(), [])
        self.assertEqual(clock.summary()["non_session_bars"], 0)

    def test_detects_missing_sessions(self):
        cal = get_calendar("XNYS")
        days = cal.sessions_between(date(2024, 3, 1), date(2024, 3, 29))
        del days[5]
        ts = [NYSE.to_ts(d) for d in days]
        clock = SessionClock.from_timestamps(ts, "XNYS")
        self.assertEqual(len(clock.missing_sessions()), 1)

    def test_horizon_date_uses_trading_days(self):
        cal = get_calendar("XNYS")
        days = cal.sessions_between(date(2024, 12, 18), date(2024, 12, 31))
        ts = [NYSE.to_ts(d) for d in days]
        clock = SessionClock.from_timestamps(ts, "XNYS")
        i = clock.index_of(date(2024, 12, 24))
        self.assertIsNotNone(i)
        # 12/24 에서 1 거래일 뒤는 12/26 (12/25 는 성탄절)
        self.assertEqual(clock.horizon_date(i, 1), date(2024, 12, 26))


class TestEpochHelpers(unittest.TestCase):
    def test_roundtrip(self):
        d = date(2025, 7, 15)
        self.assertEqual(NYSE.to_date(NYSE.to_ts(d)), d)

    def test_next_session_ts(self):
        cal = get_calendar("XNYS")
        ts = NYSE.to_ts(date(2024, 12, 24))
        self.assertEqual(NYSE.to_date(cal.next_session_ts(ts)), date(2024, 12, 26))


if __name__ == "__main__":
    unittest.main()


class TestBacktestCalendarIntegration(unittest.TestCase):
    """백테스트가 '봉 인덱스'와 '거래일'의 차이를 정직하게 보고하는가."""

    def _series_from_dates(self, days):
        from packages.chart_skills.series import Candle, OHLCV
        price = 100.0
        out = []
        for i, d in enumerate(days):
            price *= 1.001 if i % 3 else 0.999
            out.append(Candle(ts=NYSE.to_ts(d), open=price, high=price * 1.01,
                              low=price * 0.99, close=price * 1.002,
                              volume=1_000_000))
        return OHLCV(out)

    def test_reports_untrustworthy_for_synthetic_series(self):
        from packages.backtest_engine.engine import (
            BacktestEngine, buy_and_hold_strategy,
        )
        from packages.chart_skills.synth import generate_series
        eng = BacktestEngine(warmup=20, exchange="XNYS")
        res = eng.run(generate_series(seed=7, length=200), buy_and_hold_strategy())
        cal = res.leak_guard["calendar"]
        self.assertTrue(cal["checked"])
        self.assertFalse(cal["trustworthy"])
        self.assertGreater(cal["non_session_bars"], 0)
        self.assertIn("해석하면 안 됩니다", cal["reason"])

    def test_reports_trustworthy_for_real_session_series(self):
        from packages.backtest_engine.engine import (
            BacktestEngine, buy_and_hold_strategy,
        )
        cal_obj = get_calendar("XNYS")
        days = cal_obj.sessions_between(date(2023, 1, 3), date(2024, 12, 31))
        eng = BacktestEngine(warmup=20, exchange="XNYS")
        res = eng.run(self._series_from_dates(days), buy_and_hold_strategy())
        cal = res.leak_guard["calendar"]
        self.assertTrue(cal["trustworthy"], cal)
        self.assertEqual(cal["non_session_bars"], 0)
        self.assertEqual(cal["missing_sessions"], 0)

    def test_without_exchange_it_says_it_did_not_check(self):
        from packages.backtest_engine.engine import (
            BacktestEngine, buy_and_hold_strategy,
        )
        from packages.chart_skills.synth import generate_series
        eng = BacktestEngine(warmup=20)
        res = eng.run(generate_series(seed=3, length=150), buy_and_hold_strategy())
        cal = res.leak_guard["calendar"]
        self.assertFalse(cal["checked"])
        self.assertFalse(cal["trustworthy"])
