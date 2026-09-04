"""백테스트 엔진 · Pattern Miner · Point-in-Time 저장소 테스트.

여기서 검증하려는 것은 "수익이 나는가"가 아니라
"거짓말을 하지 않는가" 입니다.
"""

import unittest

from packages.backtest_engine.engine import (
    BacktestEngine,
    Signal,
    buy_and_hold_strategy,
    sma_crossover_strategy,
)
from packages.backtest_engine.metrics import max_drawdown, performance_metrics
from packages.chart_skills.series import Candle, OHLCV
from packages.chart_skills.synth import generate_series
from packages.pattern_miner.miner import PatternMiner
from packages.pit_store.store import PITError, PITStore, Record


# ====================================================================== PIT


class TestPITStore(unittest.TestCase):
    def setUp(self):
        self.s = PITStore()

    def test_future_fact_is_invisible(self):
        self.s.put_fact(Record("AAPL:rev", 100, event_time=10, published_time=20))
        self.s.put_fact(Record("AAPL:rev", 200, event_time=30, published_time=40))
        self.assertEqual(self.s.get_fact("AAPL:rev", as_of=25).value, 100)
        self.assertEqual(self.s.get_fact("AAPL:rev", as_of=45).value, 200)
        self.assertIsNone(self.s.get_fact("AAPL:rev", as_of=15))

    def test_revision_does_not_rewrite_history(self):
        """★ 정정 공시가 과거 분석을 바꾸면 안 됩니다."""
        self.s.put_fact(Record("X:rev", 124.3, event_time=100, published_time=100))
        self.s.revise_fact("X:rev", 124.1, published_time=200)
        # 2026-02-01 시점 분석 → 그때의 진실
        self.assertEqual(self.s.get_fact("X:rev", as_of=150).value, 124.3)
        # 정정 후 분석 → 새 값
        self.assertEqual(self.s.get_fact("X:rev", as_of=250).value, 124.1)

    def test_published_before_event_is_rejected(self):
        with self.assertRaises(PITError):
            Record("bad", 1, event_time=100, published_time=50)

    def test_series_view_hides_future(self):
        rows = [(i * 10, i) for i in range(20)]
        self.s.put_series("px", rows)
        view = self.s.series("px", as_of=95)
        self.assertEqual(len(view), 10)
        self.assertEqual(view.hidden_count(), 10)
        with self.assertRaises(IndexError):
            _ = view[15]

    def test_series_slice_cannot_reach_future(self):
        self.s.put_series("px", [(i, i) for i in range(100)])
        view = self.s.series("px", as_of=49)
        self.assertEqual(max(view[0:1000]), 49)

    def test_audit_reports_blocked(self):
        self.s.put_fact(Record("k", 1, event_time=1, published_time=1))
        self.s.revise_fact("k", 2, published_time=100)
        a = self.s.audit("k", as_of=50)
        self.assertEqual(a["blocked_count"], 1)
        self.assertEqual(a["visible_versions"], [1])


# ====================================================================== 지표


class TestMetrics(unittest.TestCase):
    def test_max_drawdown_known(self):
        eq = [100, 120, 90, 130]
        dd, peak, trough = max_drawdown(eq)
        self.assertAlmostEqual(dd, (90 - 120) / 120)
        self.assertEqual(peak, 1)
        self.assertEqual(trough, 2)

    def test_no_drawdown_when_monotonic(self):
        self.assertAlmostEqual(max_drawdown([100, 101, 102])[0], 0.0)

    def test_metrics_on_flat_equity(self):
        m = performance_metrics([100.0] * 50)
        self.assertAlmostEqual(m["total_return_pct"], 0.0)
        self.assertAlmostEqual(m["max_drawdown_pct"], 0.0)
        self.assertEqual(m["sharpe"], 0.0)

    def test_cagr_doubling_in_one_year(self):
        eq = [100.0 * (2 ** (i / 252)) for i in range(253)]
        m = performance_metrics(eq, periods_per_year=252)
        self.assertAlmostEqual(m["cagr_pct"], 100.0, delta=1.0)

    def test_beta_of_identical_series_is_one(self):
        rets = [0.01, -0.02, 0.03, 0.00, -0.01] * 10
        eq = [100.0]
        for r in rets:
            eq.append(eq[-1] * (1 + r))
        m = performance_metrics(eq, rets, rets)
        self.assertAlmostEqual(m["beta"], 1.0, places=6)


# ====================================================================== 백테스트


class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        self.series = generate_series(seed=101, length=400)
        self.engine = BacktestEngine(warmup=60)

    def test_runs_and_reports(self):
        r = self.engine.run(self.series, sma_crossover_strategy())
        self.assertGreater(len(r.equity), 100)
        self.assertIn("sharpe", r.metrics)

    def test_strategy_never_sees_future(self):
        """★ 전략에 넘어간 마지막 봉이 항상 '현재'여야 합니다."""
        seen_lengths = []

        def spy(past, w):
            seen_lengths.append(len(past))
            return Signal(0.0, "관찰만")

        r = self.engine.run(self.series, spy)
        # 전략은 절대 전체 길이를 보지 못합니다
        self.assertLess(max(seen_lengths), len(self.series))
        self.assertEqual(r.leak_guard["future_bars_never_shown"], 1)

    def test_strategy_cannot_index_beyond_present(self):
        """past 시리즈에는 미래 봉이 물리적으로 없습니다."""
        captured = {}

        def spy(past, w):
            captured["last_close"] = past.closes[-1]
            captured["len"] = len(past)
            return Signal(0.0, "")

        self.engine.run(self.series[:200], spy)
        # 마지막으로 본 종가는 반드시 시리즈 어딘가의 과거 값
        self.assertIn(captured["last_close"], self.series.closes[:200])

    def test_fills_happen_on_next_bar_open(self):
        """같은 봉 종가에 체결하면 그 자체가 미래 사용입니다."""
        r = self.engine.run(self.series, sma_crossover_strategy())
        for f in r.fills:
            self.assertGreater(f.index, 0)
            bar = self.series[f.index]
            # 슬리피지 범위 안에서 시가와 일치해야 함
            self.assertAlmostEqual(f.price, bar.open, delta=bar.open * 0.01)

    def test_costs_reduce_returns(self):
        cheap = BacktestEngine(commission_bps=0, slippage_bps=0, warmup=60)
        pricey = BacktestEngine(commission_bps=50, slippage_bps=50, warmup=60)
        a = cheap.run(self.series, sma_crossover_strategy())
        b = pricey.run(self.series, sma_crossover_strategy())
        self.assertGreaterEqual(a.equity[-1], b.equity[-1])

    def test_buy_and_hold_tracks_price(self):
        r = self.engine.run(self.series, buy_and_hold_strategy())
        price_ret = (self.series.closes[-1] - self.series.closes[61]) / self.series.closes[61]
        eq_ret = r.equity[-1] / r.equity[0] - 1
        self.assertAlmostEqual(eq_ret, price_ret, delta=0.06)

    def test_flat_strategy_keeps_equity_constant(self):
        r = self.engine.run(self.series, lambda past, w: Signal(0.0, "현금"))
        self.assertAlmostEqual(r.equity[0], r.equity[-1], places=6)

    def test_rejects_invalid_weight(self):
        with self.assertRaises(ValueError):
            Signal(1.5)

    def test_rejects_short_series(self):
        with self.assertRaises(ValueError):
            self.engine.run(self.series[:20], buy_and_hold_strategy())


# ====================================================================== 패턴


class TestPatternMiner(unittest.TestCase):
    def setUp(self):
        self.miner = PatternMiner(horizon=5, max_conditions=2)
        self.datasets = {
            f"S{i}": generate_series(seed=500 + i, length=600) for i in range(4)
        }

    def test_split_is_time_ordered_and_non_overlapping(self):
        split = PatternMiner.make_split(600, 60, 5)
        self.assertFalse(split.overlaps())
        self.assertLess(split.train[1], split.test[0])

    def test_mines_and_judges(self):
        pats = self.miner.mine(self.datasets)
        self.assertGreater(len(pats), 20)
        verdicts = {p.verdict for p in pats}
        self.assertTrue(verdicts & {
            "STRONG", "WEAK", "FAILED_VALIDATION", "FAILED_OUT_OF_SAMPLE",
            "NO_EDGE", "INSUFFICIENT_SAMPLE", "UNVERIFIED",
        })

    def test_most_candidates_are_rejected(self):
        """★ 대부분이 기각되는 것이 정상입니다.

        후보 대부분을 STRONG 으로 승격시키는 마이너는 고장난 것입니다.
        """
        pats = self.miner.mine(self.datasets)
        strong = [p for p in pats if p.verdict == "STRONG"]
        self.assertLess(len(strong) / len(pats), 0.5)

    def test_small_sample_never_becomes_strong(self):
        miner = PatternMiner(horizon=5, min_sample_train=10_000)
        pats = miner.mine(self.datasets)
        self.assertTrue(all(p.verdict != "STRONG" for p in pats))
        self.assertTrue(any(p.verdict == "INSUFFICIENT_SAMPLE" for p in pats))

    def test_strong_patterns_agree_across_all_three_splits(self):
        pats = self.miner.mine(self.datasets)
        for p in [x for x in pats if x.verdict == "STRONG"]:
            d1 = p.train.win_rate - 0.5
            d2 = p.validation.win_rate - 0.5
            d3 = p.test.win_rate - 0.5
            self.assertTrue(
                (d1 > 0 and d2 > 0 and d3 > 0) or (d1 < 0 and d2 < 0 and d3 < 0),
                f"{p.pattern_id}: 구간별 방향이 다릅니다",
            )

    def test_summary_shape(self):
        s = PatternMiner.summary(self.miner.mine(self.datasets))
        self.assertIn("by_verdict", s)
        self.assertIn("candidates_tested", s)

    def test_overlapping_split_is_refused(self):
        from packages.pattern_miner.miner import TimeSplit

        bad = TimeSplit((0, 100), (50, 150), (140, 200))
        self.assertTrue(bad.overlaps())


if __name__ == "__main__":
    unittest.main()


class TestPatternQualityGuards(unittest.TestCase):
    """찾은 패턴을 얼마나 잘 '의심하는가' 검증."""

    def setUp(self):
        self.datasets = {
            f"S{i}": generate_series(seed=900 + i, length=700) for i in range(4)
        }

    def test_tiny_holdout_never_becomes_strong(self):
        """홀드아웃 표본이 적으면 승률이 100%여도 STRONG 이 아닙니다."""
        m = PatternMiner(horizon=5, min_sample_holdout=25)
        for p in m.mine(self.datasets):
            if p.verdict == "STRONG":
                self.assertGreaterEqual(p.validation.sample_size, 25, p.pattern_id)
                self.assertGreaterEqual(p.test.sample_size, 25, p.pattern_id)

    def test_redundant_conditions_are_excluded(self):
        """조건을 붙였는데 표본이 그대로면 같은 패턴을 두 번 센 것입니다."""
        m = PatternMiner(horizon=5)
        pats = m.mine(self.datasets)
        by_cond = {p.conditions: p for p in pats}
        for p in pats:
            if p.verdict != "STRONG" or len(p.conditions) < 2:
                continue
            for i in range(len(p.conditions)):
                sub = tuple(c for j, c in enumerate(p.conditions) if j != i)
                parent = by_cond.get(sub)
                if parent is None:
                    continue
                self.assertFalse(
                    parent.train.sample_size == p.train.sample_size
                    and parent.test.sample_size == p.test.sample_size,
                    f"{p.pattern_id} 는 {sub} 와 같은 패턴인데 STRONG 으로 남았습니다",
                )

    def test_strong_patterns_declare_direction(self):
        for p in PatternMiner(horizon=5).mine(self.datasets):
            if p.verdict == "STRONG":
                self.assertIn(p.direction, ("UP", "DOWN"))

    def test_mock_summary_carries_loud_warning(self):
        s = PatternMiner.summary(PatternMiner(horizon=5).mine(self.datasets),
                                 data_source="MOCK_SYNTHETIC")
        self.assertTrue(s["is_mock"])
        self.assertTrue(any("합성" in w for w in s["warnings"]))
        self.assertTrue(any("겹칩" in w for w in s["warnings"]))
