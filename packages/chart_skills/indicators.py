"""기술적 지표 — 순수 파이썬 구현.

모든 함수는 입력과 같은 길이의 리스트를 돌려주며,
값이 아직 확정되지 않은 앞부분은 None 입니다.

★ 중요: None 을 0 으로 채우지 않습니다.
   "아직 모른다"와 "값이 0이다"는 완전히 다릅니다.
   0으로 채우면 백테스트가 조용히 틀립니다.
"""

from __future__ import annotations

from typing import Optional, Sequence

Num = Optional[float]


def _check(period: int) -> None:
    if period < 1:
        raise ValueError("period 는 1 이상이어야 합니다")


# ---------------------------------------------------------------- 이동평균


def sma(values: Sequence[float], period: int) -> list[Num]:
    """단순이동평균."""
    _check(period)
    out: list[Num] = [None] * len(values)
    if len(values) < period:
        return out
    running = sum(values[:period])
    out[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        out[i] = running / period
    return out


def ema(values: Sequence[float], period: int) -> list[Num]:
    """지수이동평균. 첫 값은 SMA 로 시드합니다 (업계 표준)."""
    _check(period)
    out: list[Num] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (values[i] - prev) * k + prev
        out[i] = prev
    return out


def wilder_smooth(values: Sequence[Num], period: int) -> list[Num]:
    """Wilder 평활 (RSI/ATR/ADX 에서 사용). None 은 건너뜁니다."""
    _check(period)
    out: list[Num] = [None] * len(values)
    buf: list[float] = []
    prev: Optional[float] = None
    for i, v in enumerate(values):
        if v is None:
            continue
        if prev is None:
            buf.append(v)
            if len(buf) == period:
                prev = sum(buf) / period
                out[i] = prev
        else:
            prev = (prev * (period - 1) + v) / period
            out[i] = prev
    return out


def vwap(highs, lows, closes, volumes) -> list[Num]:
    """누적 VWAP (앵커 = 시리즈 시작점)."""
    out: list[Num] = []
    pv = 0.0
    vv = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        typical = (h + l + c) / 3.0
        pv += typical * v
        vv += v
        out.append(pv / vv if vv > 0 else None)
    return out


# ---------------------------------------------------------------- 모멘텀


def rsi(closes: Sequence[float], period: int = 14) -> list[Num]:
    """Wilder RSI."""
    _check(period)
    n = len(closes)
    out: list[Num] = [None] * n
    if n <= period:
        return out

    gains: list[float] = [0.0]
    losses: list[float] = [0.0]
    for i in range(1, n):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    def _rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def macd(
    closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[Num], list[Num], list[Num]]:
    """MACD line, signal line, histogram."""
    fast_e = ema(closes, fast)
    slow_e = ema(closes, slow)
    line: list[Num] = [
        (f - s) if (f is not None and s is not None) else None for f, s in zip(fast_e, slow_e)
    ]
    valid = [v for v in line if v is not None]
    sig_vals = ema(valid, signal) if len(valid) >= signal else []
    sig: list[Num] = [None] * len(line)
    j = 0
    for i, v in enumerate(line):
        if v is None:
            continue
        if j < len(sig_vals):
            sig[i] = sig_vals[j]
        j += 1
    hist: list[Num] = [
        (m - s) if (m is not None and s is not None) else None for m, s in zip(line, sig)
    ]
    return line, sig, hist


def roc(closes: Sequence[float], period: int = 10) -> list[Num]:
    """변화율(%)."""
    _check(period)
    out: list[Num] = [None] * len(closes)
    for i in range(period, len(closes)):
        prev = closes[i - period]
        out[i] = ((closes[i] - prev) / prev * 100.0) if prev else None
    return out


def stochastic(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
    k_period: int = 14, d_period: int = 3,
) -> tuple[list[Num], list[Num]]:
    """스토캐스틱 %K, %D."""
    n = len(closes)
    k: list[Num] = [None] * n
    for i in range(k_period - 1, n):
        hh = max(highs[i - k_period + 1 : i + 1])
        ll = min(lows[i - k_period + 1 : i + 1])
        k[i] = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100.0
    valid = [v for v in k if v is not None]
    d_vals = sma(valid, d_period) if len(valid) >= d_period else []
    d: list[Num] = [None] * n
    j = 0
    for i, v in enumerate(k):
        if v is None:
            continue
        if j < len(d_vals):
            d[i] = d_vals[j]
        j += 1
    return k, d


# ---------------------------------------------------------------- 변동성


def true_range(highs, lows, closes) -> list[Num]:
    out: list[Num] = [None]
    for i in range(1, len(closes)):
        out.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return out


def atr(highs, lows, closes, period: int = 14) -> list[Num]:
    """Wilder ATR."""
    return wilder_smooth(true_range(highs, lows, closes), period)


def bollinger(
    closes: Sequence[float], period: int = 20, mult: float = 2.0
) -> tuple[list[Num], list[Num], list[Num]]:
    """볼린저밴드 (upper, middle, lower)."""
    mid = sma(closes, period)
    up: list[Num] = [None] * len(closes)
    lo: list[Num] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        m = mid[i]
        if m is None:
            continue
        var = sum((x - m) ** 2 for x in window) / period
        sd = var ** 0.5
        up[i] = m + mult * sd
        lo[i] = m - mult * sd
    return up, mid, lo


def adx(highs, lows, closes, period: int = 14) -> list[Num]:
    """ADX (추세 강도). Wilder 방식."""
    n = len(closes)
    out: list[Num] = [None] * n
    if n < period * 2 + 1:
        return out

    plus_dm: list[Num] = [None]
    minus_dm: list[Num] = [None]
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)

    tr = true_range(highs, lows, closes)
    atr_s = wilder_smooth(tr, period)
    pdm_s = wilder_smooth(plus_dm, period)
    mdm_s = wilder_smooth(minus_dm, period)

    dx: list[Num] = [None] * n
    for i in range(n):
        a, p, m = atr_s[i], pdm_s[i], mdm_s[i]
        if a is None or p is None or m is None or a == 0:
            continue
        pdi = 100.0 * p / a
        mdi = 100.0 * m / a
        denom = pdi + mdi
        dx[i] = 0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom

    return wilder_smooth(dx, period)


# ---------------------------------------------------------------- 거래량


def obv(closes: Sequence[float], volumes: Sequence[float]) -> list[Num]:
    """On-Balance Volume."""
    out: list[Num] = [0.0]
    for i in range(1, len(closes)):
        prev = out[i - 1] or 0.0
        if closes[i] > closes[i - 1]:
            out.append(prev + volumes[i])
        elif closes[i] < closes[i - 1]:
            out.append(prev - volumes[i])
        else:
            out.append(prev)
    return out


def relative_volume(volumes: Sequence[float], period: int = 20) -> list[Num]:
    """RVOL — 최근 거래량 / 평균 거래량."""
    avg = sma(volumes, period)
    out: list[Num] = [None] * len(volumes)
    for i, a in enumerate(avg):
        if a and a > 0:
            out[i] = volumes[i] / a
    return out


def relative_strength(closes: Sequence[float], bench: Sequence[float], period: int = 20) -> list[Num]:
    """벤치마크 대비 상대강도 (기간 수익률 차이, %p)."""
    a = roc(closes, period)
    b = roc(bench, period)
    return [(x - y) if (x is not None and y is not None) else None for x, y in zip(a, b)]
