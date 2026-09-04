"""영속화 계층.

기본 백엔드는 **SQLite** 입니다 (파이썬 표준 라이브러리, 설치 불필요).
PostgreSQL 을 쓰고 싶으면 `PostgresStore` 를 쓰되 psycopg 가 필요합니다.
"""

from .store import (
    PersistenceError,
    SqliteStore,
    Store,
    open_store,
)
from .snapshot import EngineSnapshot, restore_engine, snapshot_engine

__all__ = [
    "PersistenceError",
    "SqliteStore",
    "Store",
    "open_store",
    "EngineSnapshot",
    "snapshot_engine",
    "restore_engine",
]
