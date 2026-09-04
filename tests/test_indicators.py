"""지표 계산 테스트 — 손으로 계산한 값과 대조합니다.

지표가 틀리면 그 위의 학습·백테스트가 전부 조용히 틀립니다.
그래서 여기가 가장 아래쪽 안전망입니다.
"""

import unittest

from packages.chart_skills.indicators import (
    adx,
    atr,
    bollinger,
    ema,
    macd,
    obv,
    relative_volume,
    roc,
    rsi,
    sma,
    true_range,
    vwap,
)
from packages.chart_skills.series import Candle, OHLCV


class TestSMA(unittest.TestCase):
    def test_known_values(self):
        v = [1, 2, 3, 4, 5]
        out = sma(v, 3)
        self.assertEqual(out[:2], [None, None])   # 아직 모르는 구간은 None
        self.assertAlmostEqual(out[2], 2.0)
        self.assertAlmostEqual(out[3], 3.0)
        self.assertAlmostEqual(out[4], 4.0)

    def test_never_fills_none_with_zero(self):
        """None 을 0으로 채우면 백테스트가 조용히 틀립니다."""
        out = sma([1, 2, 3], 5)
        self.assertTrue(all(x is None for x in out))

    def test_rolling_matches_naive(self):
        v = [3.5, 1.2, 8.8, 4.4, 9.1, 2.2, 7.7, 5.5]
        out = sma(v, 4)
        for i in range(3, len(v)):
            self.assertAlmostEqual(out[i], sum(v[i - 3 : i + 1]) / 4, places=9)

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            sma([1, 2, 3], 0)


class TestEMA(unittest.TestCase):
    def test_seed_is_sma(self):
        v = [1, 2, 3, 4, 5, 6]
        out = ema(v, 3)
        self.assertAlmostEqual(out[2], 2.0)       # (1+2+3)/3
        k = 2 / 4
        self.assertAlmostEqual(out[3], (4 - 2.0) * k + 2.0)

    def test_constant_series_stays_constant(self):
        out = ema([7.0] * 20, 5)
        for x in out[4:]:
            self.assertAlmostEqual(x, 7.0)


class TestRSI(unittest.TestCase):
    def test_all_gains_is_100(self):
        v = list(range(1, 40))
        out = rsi(v, 14)
        self.assertAlmostEqual(out[-1], 100.0)

    def test_all_losses_is_zero(self):
        v = list(range(40, 1, -1))
        out = rsi(v, 14)
        self.assertAlmostEqual(out[-1], 0.0, places=6)

    def test_bounds(self):
        import random

        rng = random.Random(4)
        v = [100.0]
        for _ in range(200):
            v.append(max(1.0, v[-1] * (1 + rng.gauss(0, 0.02))))
        for x in rsi(v, 14):
            if x is not None:
                self.assertGreaterEqual(x, 0.0)
                self.assertLessEqual(x, 100.0)

    def test_warmup_is_none(self):
        v = list(range(1, 30))
        out = rsi(v, 14)
        self.assertTrue(all(x is None for x in out[:14]))
        self.assertIsNotNone(out[14])


class TestATR(unittest.TestCase):
    def test_true_range_known(self):
        h = [10, 12, 11]
        l = [8, 9, 7]
        c = [9, 11, 8]
        tr = true_range(h, l, c)
        self.assertIsNone(tr[0])
        # max(12-9, |12-9|, |9-9|) = 3
        self.assertAlmostEqual(tr[1], 3.0)
        # max(11-7, |11-11|, |7-11|) = 4
        self.assertAlmostEqual(tr[2], 4.0)

    def test_atr_positive(self):
        from packages.chart_skills.synth import generate_series

        s = generate_series(seed=1, length=120)
        out = atr(s.highs, s.lows, s.closes, 14)
        vals = [x for x in out if x is not None]
        self.assertTrue(vals)
        self.assertTrue(all(x > 0 for x in vals))


class TestMACD(unittest.TestCase):
    def test_hist_is_line_minus_signal(self):
        from packages.chart_skills.synth import generate_series

        s = generate_series(seed=2, length=200)
        line, sig, hist = macd(s.closes)
        for m, g, h in zip(line, sig, hist):
            if m is not None and g is not None:
                self.assertAlmostEqual(h, m - g, places=9)
            else:
                self.assertIsNone(h)


class TestADX(unittest.TestCase):
    def test_range_0_100(self):
        from packages.chart_skills.synth import generate_series

        s = generate_series(seed=3, length=300)
        for x in adx(s.highs, s.lows, s.closes, 14):
            if x is not None:
                self.assertGreaterEqual(x, 0.0)
                self.assertLessEqual(x, 100.0)

    def test_strong_trend_has_high_adx(self):
        n = 120
        c = [100 * (1.01 ** i) for i in range(n)]
        h = [x * 1.005 for x in c]
        l = [x * 0.995 for x in c]
        vals = [x for x in adx(h, l, c, 14) if x is not None]
        self.assertTrue(vals)
        self.assertGreater(vals[-1], 40.0)   # 일방향 추세면 ADX 가 높아야 함


class TestBollinger(unittest.TestCase):
    def test_ordering(self):
        from packages.chart_skills.synth import generate_series

        s = generate_series(seed=5, length=150)
        up, mid, lo = bollinger(s.closes, 20, 2.0)
        for u, m, d in zip(up, mid, lo):
            if u is not None:
                self.assertGreaterEqual(u, m)
                self.assertGreaterEqual(m, d)

    def test_constant_series_zero_width(self):
        up, mid, lo = bollinger([5.0] * 40, 20, 2.0)
        self.assertAlmostEqual(up[-1], 5.0)
        self.assertAlmostEqual(lo[-1], 5.0)


class TestVolume(unittest.TestCase):
    def test_obv_direction(self):
        c = [10, 11, 10, 12]
        v = [100, 200, 300, 400]
        out = obv(c, v)
        self.assertEqual(out, [0.0, 200.0, -100.0, 300.0])

    def test_rvol_one_for_constant(self):
        out = relative_volume([100.0] * 40, 20)
        self.assertAlmostEqual(out[-1], 1.0)

    def test_vwap_between_low_and_high(self):
        from packages.chart_skills.synth import generate_series

        s = generate_series(seed=6, length=80)
        out = vwap(s.highs, s.lows, s.closes, s.volumes)
        self.assertGreaterEqual(out[-1], min(s.lows))
        self.assertLessEqual(out[-1], max(s.highs))


class TestROC(unittest.TestCase):
    def test_known(self):
        v = [100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 110]
        self.assertAlmostEqual(roc(v, 10)[10], 10.0)


class TestResample(unittest.TestCase):
    def test_weekly_from_daily(self):
        candles = [
            Candle(ts=i, open=i + 1, high=i + 3, low=i, close=i + 2, volume=10)
            for i in range(10)
        ]
        s = OHLCV(candles)
        w = s.resample(5)
        self.assertEqual(len(w), 2)
        self.assertEqual(w[0].open, candles[0].open)
        self.assertEqual(w[0].close, candles[4].close)
        self.assertEqual(w[0].high, max(c.high for c in candles[:5]))
        self.assertEqual(w[0].volume, 50)

    def test_drops_incomplete_bucket(self):
        """미완성 캔들을 완성된 것처럼 쓰면 안 됩니다."""
        candles = [
            Candle(ts=i, open=1, high=2, low=0, close=1, volume=1) for i in range(7)
        ]
        self.assertEqual(len(OHLCV(candles).resample(5)), 1)


if __name__ == "__main__":
    unittest.main()
