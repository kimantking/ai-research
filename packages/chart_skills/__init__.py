"""차트 스킬 — 지표 계산, 시장 구조 분석, 학습용 캔들 생성.

Phase 4~7 에서는 외부 의존성 없이 순수 파이썬으로 구현합니다.
Phase 16 에서 pandas-ta-classic / TA-Lib 로 확장하되,
여기 함수들은 그때 '정답 대조용 기준값'으로 계속 남습니다.
"""

from .indicators import (
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
    stochastic,
    vwap,
)
from .series import Candle, OHLCV
from .structure import market_structure
from .synth import generate_series

__all__ = [
    "Candle", "OHLCV", "generate_series", "market_structure",
    "sma", "ema", "vwap", "rsi", "macd", "atr", "adx",
    "bollinger", "stochastic", "roc", "obv", "relative_volume",
]
