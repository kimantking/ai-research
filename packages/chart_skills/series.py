"""OHLCV 자료구조.

pandas 없이도 동작하게 만들어 둡니다. Phase 16 에서 pandas 로 바꿔도
이 인터페이스는 유지합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Candle:
    ts: int          # epoch seconds
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "o": round(self.open, 4),
            "h": round(self.high, 4),
            "l": round(self.low, 4),
            "c": round(self.close, 4),
            "v": round(self.volume, 2),
        }


class OHLCV:
    """캔들 시계열. 슬라이싱하면 같은 타입이 나옵니다."""

    __slots__ = ("candles",)

    def __init__(self, candles: Iterable[Candle]):
        self.candles: list[Candle] = list(candles)

    # ---- 기본 ----
    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return OHLCV(self.candles[item])
        return self.candles[item]

    def __iter__(self):
        return iter(self.candles)

    # ---- 컬럼 접근 ----
    @property
    def opens(self) -> list[float]:
        return [c.open for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def volumes(self) -> list[float]:
        return [c.volume for c in self.candles]

    def to_list(self) -> list[dict]:
        return [c.as_dict() for c in self.candles]

    # ---- 리샘플링 (일봉 -> 주봉/월봉 등) ----
    def resample(self, factor: int) -> "OHLCV":
        """factor 개씩 묶어 상위 타임프레임으로 만듭니다.

        예: 일봉에서 factor=5 → 주봉 근사.
        마지막 미완성 묶음은 버립니다 (미완성 캔들로 판단하면 안 되므로).
        """
        if factor <= 1:
            return OHLCV(self.candles)
        out: list[Candle] = []
        for i in range(0, len(self.candles) - factor + 1, factor):
            chunk: Sequence[Candle] = self.candles[i : i + factor]
            out.append(
                Candle(
                    ts=chunk[0].ts,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                )
            )
        return OHLCV(out)
