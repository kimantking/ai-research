"""실제 시장 데이터 공급자.

★ 설계 원칙
    1. 네트워크 호출은 **주입 가능한 transport** 뒤에 둡니다.
       그래야 인터넷 없이도 파서와 정규화 로직을 전부 테스트할 수 있습니다.
    2. 어떤 공급자든 같은 `Bars` 를 돌려줍니다.
    3. 조정주가(adjusted)와 원주가(raw)를 절대 섞지 않습니다.
    4. 실패는 조용히 넘어가지 않고 이유를 남깁니다.
"""

from .base import (
    Bars,
    DataQualityReport,
    MarketDataError,
    Provider,
    ProviderResult,
    Transport,
    UrlTransport,
)
from .csv_provider import CsvFileProvider
from .data_go_kr import DataGoKrProvider
from .stooq import StooqProvider
from .yfinance_provider import YFinanceProvider
from .ingest import ingest_bars, to_ohlcv

__all__ = [
    "Bars",
    "DataQualityReport",
    "MarketDataError",
    "Provider",
    "ProviderResult",
    "Transport",
    "UrlTransport",
    "CsvFileProvider",
    "DataGoKrProvider",
    "StooqProvider",
    "YFinanceProvider",
    "ingest_bars",
    "to_ohlcv",
]
