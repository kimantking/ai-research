"""차트 특징 추출.

★ Point-in-Time 안전장치
   이 함수에는 '과거 캔들만' 담긴 시리즈를 넘깁니다.
   미래 캔들은 애초에 전달되지 않으므로, 실수로 미래를 볼 방법이 없습니다.
   (프롬프트로 "보지 마세요"라고 부탁하는 방식이 아닙니다.)
"""

from __future__ import annotations

import math

from packages.chart_skills.indicators import (
    adx,
    atr,
    bollinger,
    macd,
    relative_volume,
    roc,
    rsi,
    sma,
)
from packages.chart_skills.series import OHLCV

FEATURE_NAMES = [
    "rsi14_z",        # RSI 를 -1~1 로 정규화
    "macd_hist_n",    # MACD 히스토그램 / 가격
    "trend_sma",      # (종가 - SMA20) / ATR
    "sma_cross",      # (SMA20 - SMA50) / 가격
    "roc10_n",        # 10일 변화율
    "atr_pct_z",      # 변동성 수준
    "rvol_z",         # 상대 거래량
    "bb_pos",         # 볼린저밴드 내 위치 (-1 하단 ~ +1 상단)
    "adx_n",          # 추세 강도
    "bias",           # 상수항
]

MIN_BARS = 60


def _clip(x: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return max(lo, min(hi, x))


def _safe(x, default=0.0):
    return default if x is None or (isinstance(x, float) and math.isnan(x)) else x


def extract_features(past: OHLCV) -> list[float] | None:
    """과거 캔들만으로 특징 벡터를 만듭니다. 데이터가 부족하면 None."""
    if len(past) < MIN_BARS:
        return None

    closes, highs, lows, vols = past.closes, past.highs, past.lows, past.volumes
    last = closes[-1]
    if last <= 0:
        return None

    rsi14 = _safe(rsi(closes, 14)[-1], 50.0)
    _, _, hist = macd(closes)
    macd_h = _safe(hist[-1], 0.0)
    sma20 = _safe(sma(closes, 20)[-1], last)
    sma50 = _safe(sma(closes, 50)[-1], last)
    atr14 = _safe(atr(highs, lows, closes, 14)[-1], last * 0.02) or last * 0.02
    roc10 = _safe(roc(closes, 10)[-1], 0.0)
    rvol = _safe(relative_volume(vols, 20)[-1], 1.0)
    up, mid, lo = bollinger(closes, 20, 2.0)
    adx14 = _safe(adx(highs, lows, closes, 14)[-1], 20.0)

    if up[-1] is not None and lo[-1] is not None and up[-1] != lo[-1]:
        bb_pos = (last - lo[-1]) / (up[-1] - lo[-1]) * 2.0 - 1.0
    else:
        bb_pos = 0.0

    return [
        _clip((rsi14 - 50.0) / 25.0),
        _clip(macd_h / last * 100.0),
        _clip((last - sma20) / atr14 / 2.0),
        _clip((sma20 - sma50) / last * 50.0),
        _clip(roc10 / 10.0),
        _clip((atr14 / last * 100.0 - 2.0) / 2.0),
        _clip((rvol - 1.0) * 1.5),
        _clip(bb_pos),
        _clip((adx14 - 20.0) / 15.0),
        1.0,  # bias
    ]
