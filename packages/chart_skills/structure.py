"""시장 구조 분석 — HH/HL/LH/LL, 지지/저항, 추세, 돌파.

★ 주의 (프로젝트 원칙 §14)
   여기서 나오는 "패턴"은 통계적 경향이지 물리 법칙이 아닙니다.
   패턴 이름 자체를 근거로 삼지 않고, 표본 수와 과거 성과를 함께 봅니다.
"""

from __future__ import annotations

from .indicators import adx, atr, relative_volume, rsi, sma
from .series import OHLCV


def _swing_points(values: list[float], k: int = 3) -> tuple[list[int], list[int]]:
    """좌우 k개보다 높으면 스윙 고점, 낮으면 스윙 저점."""
    highs_idx: list[int] = []
    lows_idx: list[int] = []
    for i in range(k, len(values) - k):
        window = values[i - k : i + k + 1]
        if values[i] == max(window) and window.count(values[i]) == 1:
            highs_idx.append(i)
        if values[i] == min(window) and window.count(values[i]) == 1:
            lows_idx.append(i)
    return highs_idx, lows_idx


def market_structure(series: OHLCV, lookback: int = 120) -> dict:
    """시장 구조 요약. 에이전트에게 넘길 '숫자 컨텍스트'."""
    s = series[-lookback:] if len(series) > lookback else series
    closes, highs, lows, vols = s.closes, s.highs, s.lows, s.volumes
    n = len(closes)
    if n < 20:
        return {"error": "데이터 부족", "bars": n}

    hi_idx, lo_idx = _swing_points(highs, 3)
    lo_idx2 = _swing_points(lows, 3)[1]

    swing_highs = [highs[i] for i in hi_idx][-3:]
    swing_lows = [lows[i] for i in lo_idx2][-3:]

    hh = len(swing_highs) >= 2 and swing_highs[-1] > swing_highs[-2]
    lh = len(swing_highs) >= 2 and swing_highs[-1] < swing_highs[-2]
    hl = len(swing_lows) >= 2 and swing_lows[-1] > swing_lows[-2]
    ll = len(swing_lows) >= 2 and swing_lows[-1] < swing_lows[-2]

    if hh and hl:
        trend = "uptrend"
    elif lh and ll:
        trend = "downtrend"
    else:
        trend = "range"

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50) if n >= 50 else [None] * n
    adx14 = adx(highs, lows, closes, 14)
    atr14 = atr(highs, lows, closes, 14)
    rsi14 = rsi(closes, 14)
    rvol = relative_volume(vols, 20)

    last = closes[-1]
    resistance = max(swing_highs) if swing_highs else max(highs)
    support = min(swing_lows) if swing_lows else min(lows)

    atr_now = atr14[-1] or (last * 0.02)
    breakout = last > resistance - atr_now * 0.1
    breakdown = last < support + atr_now * 0.1

    def r(x, nd=4):
        return None if x is None else round(x, nd)

    return {
        "bars": n,
        "last_close": r(last),
        "trend": trend,
        "structure": {"HH": hh, "HL": hl, "LH": lh, "LL": ll},
        "support": r(support),
        "resistance": r(resistance),
        "distance_to_resistance_pct": r((resistance - last) / last * 100, 2),
        "distance_to_support_pct": r((last - support) / last * 100, 2),
        "breakout": breakout,
        "breakdown": breakdown,
        "sma20": r(sma20[-1]),
        "sma50": r(sma50[-1]),
        "above_sma20": (sma20[-1] is not None and last > sma20[-1]),
        "adx14": r(adx14[-1], 2),
        "atr14": r(atr14[-1]),
        "atr_pct": r((atr_now / last) * 100, 2),
        "rsi14": r(rsi14[-1], 2),
        "rvol20": r(rvol[-1], 2),
        # ★ 이 문구는 리포트에 항상 따라붙습니다.
        "disclaimer": "기술적 신호는 통계적 경향이며 확정된 예측이 아닙니다.",
    }
