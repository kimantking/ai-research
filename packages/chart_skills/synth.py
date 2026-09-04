"""학습·데모용 합성 캔들 생성기.

★ 왜 합성 데이터인가
   Phase 4~7 단계에서는 외부 데이터 공급자를 연결하지 않습니다.
   그런데 "학습"을 진짜로 돌리려면 캔들이 필요합니다.
   그래서 시드 고정 난수로 재현 가능한 시계열을 만듭니다.

★ 정직성
   이것은 실제 시장 데이터가 아닙니다. 여기서 나온 모든 데이터에는
   is_mock=True 가 붙고 UI 에 MOCK DATA 배지가 뜹니다.
   Phase 11 에서 실제 공급자로 교체하면 학습 코드는 그대로 씁니다.
"""

from __future__ import annotations

import math
import random

from .series import Candle, OHLCV

_DAY = 86_400


def generate_series(
    seed: int,
    length: int = 400,
    start_price: float = 100.0,
    start_ts: int = 1_600_000_000,
    interval: int = _DAY,
    regime: str | None = None,
) -> OHLCV:
    """재현 가능한 OHLCV 를 만듭니다.

    같은 seed 는 언제나 같은 결과를 냅니다 (테스트/백테스트 재현성).
    regime: "trend_up" | "trend_down" | "range" | "volatile" | None(자동)
    """
    rng = random.Random(seed)

    if regime is None:
        regime = rng.choice(["trend_up", "trend_down", "range", "volatile"])

    drift, vol, mean_rev = {
        "trend_up":   (0.0009, 0.016, 0.00),
        "trend_down": (-0.0009, 0.017, 0.00),
        "range":      (0.0000, 0.011, 0.05),
        "volatile":   (0.0002, 0.032, 0.00),
    }[regime]

    candles: list[Candle] = []
    price = start_price
    anchor = start_price
    base_vol = rng.uniform(800_000, 3_000_000)

    for i in range(length):
        # 완만한 사이클을 하나 얹어 현실감을 준다
        cycle = math.sin(i / 27.0) * vol * 0.35
        pull = (anchor - price) / anchor * mean_rev
        ret = rng.gauss(drift + pull + cycle, vol)

        open_ = price
        close = max(0.5, open_ * (1.0 + ret))
        span = abs(close - open_) + open_ * rng.uniform(0.002, 0.012)
        high = max(open_, close) + span * rng.uniform(0.1, 0.6)
        low = max(0.1, min(open_, close) - span * rng.uniform(0.1, 0.6))

        # 큰 변동일수록 거래량이 는다 (실제 시장의 성질)
        vol_mult = 1.0 + abs(ret) / max(vol, 1e-9) * 0.7
        volume = base_vol * vol_mult * rng.uniform(0.7, 1.35)

        candles.append(
            Candle(ts=start_ts + i * interval, open=open_, high=high, low=low,
                   close=close, volume=volume)
        )
        price = close
        if i % 60 == 0:
            anchor = price

    return OHLCV(candles)


def series_regime(series: OHLCV, lookback: int = 60) -> str:
    """시계열의 최근 국면을 단순 규칙으로 분류합니다 (라벨링용)."""
    closes = series.closes[-lookback:]
    if len(closes) < 10:
        return "unknown"
    total = (closes[-1] - closes[0]) / closes[0]
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
    if sd > 0.028:
        return "volatile"
    if total > 0.08:
        return "trend_up"
    if total < -0.08:
        return "trend_down"
    return "range"
