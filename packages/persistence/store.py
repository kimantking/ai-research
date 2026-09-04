"""SQLite 기반 영속 저장소.

★ 왜 SQLite 인가 (PostgreSQL 이 아니라)

    지금까지 이 시스템의 가장 아픈 제한은 이것이었습니다.

        "껐다 켜면 학습 기록이 전부 사라진다."

    에이전트가 4시간 공부해서 모델 가중치를 고쳐놨는데, 재시작하면
    처음부터 다시 시작합니다. 그러면 "매일 학습한다"는 말이 거짓말이 됩니다.

    PostgreSQL 은 Docker 가 켜져 있어야 하고, 드라이버(psycopg)가 필요하고,
    비밀번호 설정이 필요합니다. 이 중 하나라도 없으면 그냥 안 돕니다.

    SQLite 는 파이썬에 들어 있습니다. 파일 하나면 끝입니다.
    **오늘 당장** 학습이 이어집니다. PostgreSQL 은 여러 대에서 같이 쓸 때
    필요해지며, 그때를 위해 같은 인터페이스(`Store`)를 만들어 두었습니다.

★ 설계 규칙

    1. 스키마는 버전이 있고, 마이그레이션은 앞으로만 갑니다.
    2. PIT 원칙: 사실은 UPDATE 하지 않고 새 행을 INSERT 합니다.
    3. 어떤 저장 실패도 시스템을 멈추지 않습니다 (best-effort).
       메모리가 진실의 원본이고, DB 는 그것을 다음 실행까지 옮기는 통로입니다.
    4. API 키·비밀번호는 절대 저장하지 않습니다.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

SCHEMA_VERSION = 3


class PersistenceError(RuntimeError):
    """저장소를 열 수조차 없을 때만 발생합니다."""


# ------------------------------------------------------------------ 인터페이스
class Store(Protocol):
    """백엔드가 지켜야 하는 최소 계약."""

    def put_kv(self, namespace: str, key: str, value: Any) -> None: ...
    def get_kv(self, namespace: str, key: str, default: Any = None) -> Any: ...
    def list_kv(self, namespace: str) -> dict[str, Any]: ...
    def append_event(self, kind: str, payload: dict) -> int: ...
    def recent_events(self, limit: int = 200, kind: str | None = None) -> list[dict]: ...
    def upsert_prediction(self, pred: dict) -> None: ...
    def predictions(self, limit: int = 500) -> list[dict]: ...
    def put_fact(self, key: str, value: Any, published_time: int,
                 event_time: int, source_id: str, confidence: float) -> int: ...
    def facts_as_of(self, key: str, as_of: int) -> list[dict]: ...
    def stats(self) -> dict: ...
    def close(self) -> None: ...


# ------------------------------------------------------------------ 마이그레이션
_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kv (
            namespace TEXT NOT NULL,
            key       TEXT NOT NULL,
            value     TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (namespace, key)
        );
        CREATE TABLE IF NOT EXISTS events (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      REAL NOT NULL,
            kind    TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, id DESC);
    """),
    (2, """
        CREATE TABLE IF NOT EXISTS predictions (
            pred_id     TEXT PRIMARY KEY,
            agent_id    TEXT NOT NULL,
            ticker      TEXT,
            direction   TEXT,
            confidence  REAL,
            created_ts  REAL NOT NULL,
            payload     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pred_agent ON predictions(agent_id);
    """),
    (3, """
        -- ★ Point-in-Time: 정정은 UPDATE 가 아니라 새 버전 INSERT 입니다.
        CREATE TABLE IF NOT EXISTS facts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            key            TEXT NOT NULL,
            value          TEXT NOT NULL,
            event_time     INTEGER NOT NULL,
            published_time INTEGER NOT NULL,
            received_time  INTEGER NOT NULL,
            source_id      TEXT NOT NULL DEFAULT '',
            confidence     REAL NOT NULL DEFAULT 1.0,
            version        INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_facts_key_pub
            ON facts(key, published_time);
        CREATE TABLE IF NOT EXISTS bars (
            symbol   TEXT NOT NULL,
            ts       INTEGER NOT NULL,
            o REAL, h REAL, l REAL, c REAL, v REAL,
            source   TEXT NOT NULL DEFAULT '',
            adjusted INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (symbol, ts)
        );
    """),
]


# ------------------------------------------------------------------ SQLite
class SqliteStore:
    """파일 하나로 끝나는 저장소. 스레드 안전(직렬화)."""

    def __init__(self, path: str | Path, timeout: float = 5.0):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(
                str(self.path), timeout=timeout, check_same_thread=False
            )
        except sqlite3.Error as exc:                     # pragma: no cover
            raise PersistenceError(f"저장소를 열 수 없습니다: {exc}") from exc
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._configure()
        self._migrate()

    backend = "sqlite"

    # ---- 내부 ----
    def _configure(self) -> None:
        with self._lock:
            # WAL: 읽기와 쓰기가 서로를 막지 않습니다.
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

    def _migrate(self) -> None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
            )
            current = 0
            if cur.fetchone():
                row = self._conn.execute(
                    "SELECT version FROM schema_meta WHERE id=1").fetchone()
                current = row["version"] if row else 0

            for version, sql in _MIGRATIONS:
                if version <= current:
                    continue
                self._conn.executescript(sql)
                now = time.time()
                self._conn.execute(
                    "INSERT INTO schema_meta (id, version, created_at, updated_at) "
                    "VALUES (1, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET version=?, updated_at=?",
                    (version, now, now, version, now),
                )
                self._conn.commit()

    @property
    def schema_version(self) -> int:
        row = self._conn.execute(
            "SELECT version FROM schema_meta WHERE id=1").fetchone()
        return row["version"] if row else 0

    # ---- key/value ----
    def put_kv(self, namespace: str, key: str, value: Any) -> None:
        blob = json.dumps(value, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv (namespace, key, value, updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=?, updated_at=?",
                (namespace, key, blob, time.time(), blob, time.time()),
            )
            self._conn.commit()

    def put_many_kv(self, namespace: str, items: dict[str, Any]) -> None:
        """한 트랜잭션으로 묶어 씁니다 (에이전트 177명을 매번 개별 커밋하면 느립니다)."""
        now = time.time()
        rows = [(namespace, k, json.dumps(v, ensure_ascii=False, default=str), now,
                 json.dumps(v, ensure_ascii=False, default=str), now)
                for k, v in items.items()]
        with self._lock:
            self._conn.executemany(
                "INSERT INTO kv (namespace, key, value, updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=?, updated_at=?",
                rows,
            )
            self._conn.commit()

    def get_kv(self, namespace: str, key: str, default: Any = None) -> Any:
        row = self._conn.execute(
            "SELECT value FROM kv WHERE namespace=? AND key=?", (namespace, key)
        ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def list_kv(self, namespace: str) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT key, value FROM kv WHERE namespace=?", (namespace,)
        ).fetchall()
        out: dict[str, Any] = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except json.JSONDecodeError:
                continue
        return out

    def delete_kv(self, namespace: str, key: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM kv WHERE namespace=? AND key=?", (namespace, key))
            self._conn.commit()

    # ---- 이벤트 ----
    def append_event(self, kind: str, payload: dict) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts, kind, payload) VALUES (?,?,?)",
                (time.time(), kind, json.dumps(payload, ensure_ascii=False, default=str)),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def append_events(self, items: Iterable[tuple[str, dict]]) -> int:
        rows = [(time.time(), k, json.dumps(p, ensure_ascii=False, default=str))
                for k, p in items]
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                "INSERT INTO events (ts, kind, payload) VALUES (?,?,?)", rows)
            self._conn.commit()
        return len(rows)

    def recent_events(self, limit: int = 200, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE kind=? ORDER BY id DESC LIMIT ?",
                (kind, limit)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except json.JSONDecodeError:
                payload = {}
            out.append({"id": r["id"], "ts": r["ts"], "kind": r["kind"], **payload})
        return out

    def prune_events(self, keep: int = 20_000) -> int:
        """무한히 쌓이지 않게 오래된 이벤트를 잘라냅니다."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()
            n = row["n"]
            if n <= keep:
                return 0
            cutoff = self._conn.execute(
                "SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?", (keep,)
            ).fetchone()
            if cutoff is None:
                return 0
            cur = self._conn.execute("DELETE FROM events WHERE id <= ?", (cutoff["id"],))
            self._conn.commit()
            return cur.rowcount

    # ---- 예측 ----
    def upsert_prediction(self, pred: dict) -> None:
        pid = str(pred.get("id") or pred.get("pred_id") or "")
        if not pid:
            return
        blob = json.dumps(pred, ensure_ascii=False, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO predictions "
                "(pred_id, agent_id, ticker, direction, confidence, created_ts, payload) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(pred_id) DO UPDATE SET payload=?, direction=?, confidence=?",
                (pid, str(pred.get("agent_id", "")), str(pred.get("ticker", "")),
                 str(pred.get("direction", "")), float(pred.get("confidence") or 0.0),
                 time.time(), blob,
                 blob, str(pred.get("direction", "")),
                 float(pred.get("confidence") or 0.0)),
            )
            self._conn.commit()

    def upsert_predictions(self, preds: Sequence[dict]) -> int:
        n = 0
        with self._lock:
            for p in preds:
                pid = str(p.get("id") or p.get("pred_id") or "")
                if not pid:
                    continue
                blob = json.dumps(p, ensure_ascii=False, default=str)
                self._conn.execute(
                    "INSERT INTO predictions "
                    "(pred_id, agent_id, ticker, direction, confidence, created_ts, payload) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(pred_id) DO UPDATE SET payload=?",
                    (pid, str(p.get("agent_id", "")), str(p.get("ticker", "")),
                     str(p.get("direction", "")), float(p.get("confidence") or 0.0),
                     time.time(), blob, blob),
                )
                n += 1
            self._conn.commit()
        return n

    def predictions(self, limit: int = 500) -> list[dict]:
        rows = self._conn.execute(
            "SELECT payload FROM predictions ORDER BY created_ts DESC LIMIT ?",
            (limit,)).fetchall()
        out = []
        for r in rows:
            try:
                out.append(json.loads(r["payload"]))
            except json.JSONDecodeError:
                continue
        return out

    # ---- Point-in-Time 사실 ----
    def put_fact(self, key: str, value: Any, published_time: int,
                 event_time: int, source_id: str = "",
                 confidence: float = 1.0) -> int:
        """★ 정정이 들어와도 기존 행을 고치지 않습니다. 새 버전을 넣습니다."""
        if published_time < event_time:
            raise PersistenceError(
                f"published_time 이 event_time 보다 앞섭니다: {key}")
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(version) AS v FROM facts WHERE key=?", (key,)).fetchone()
            version = (row["v"] or 0) + 1
            cur = self._conn.execute(
                "INSERT INTO facts "
                "(key, value, event_time, published_time, received_time, "
                " source_id, confidence, version) VALUES (?,?,?,?,?,?,?,?)",
                (key, json.dumps(value, ensure_ascii=False, default=str),
                 event_time, published_time, int(time.time()),
                 source_id, confidence, version),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def facts_as_of(self, key: str, as_of: int) -> list[dict]:
        """as_of 시점에 **공개되어 있던** 버전만 돌려줍니다."""
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE key=? AND published_time <= ? "
            "ORDER BY published_time ASC, version ASC",
            (key, as_of)).fetchall()
        out = []
        for r in rows:
            try:
                value = json.loads(r["value"])
            except json.JSONDecodeError:
                value = None
            out.append({
                "key": r["key"], "value": value, "version": r["version"],
                "event_time": r["event_time"], "published_time": r["published_time"],
                "received_time": r["received_time"], "source_id": r["source_id"],
                "confidence": r["confidence"],
            })
        return out

    def latest_fact_as_of(self, key: str, as_of: int) -> dict | None:
        rows = self.facts_as_of(key, as_of)
        return rows[-1] if rows else None

    # ---- 캔들 ----
    def put_bars(self, symbol: str, bars: Sequence[dict], source: str = "",
                 adjusted: bool = False) -> int:
        rows = [(symbol, int(b["ts"]), float(b["o"]), float(b["h"]), float(b["l"]),
                 float(b["c"]), float(b["v"]), source, 1 if adjusted else 0)
                for b in bars]
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                "INSERT INTO bars (symbol, ts, o, h, l, c, v, source, adjusted) "
                "VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(symbol, ts) DO UPDATE SET "
                "o=excluded.o, h=excluded.h, l=excluded.l, c=excluded.c, "
                "v=excluded.v, source=excluded.source, adjusted=excluded.adjusted",
                rows)
            self._conn.commit()
        return len(rows)

    def get_bars(self, symbol: str, start_ts: int = 0,
                 end_ts: int | None = None, limit: int = 5000) -> list[dict]:
        end_ts = end_ts if end_ts is not None else 2 ** 62
        rows = self._conn.execute(
            "SELECT ts, o, h, l, c, v, source, adjusted FROM bars "
            "WHERE symbol=? AND ts BETWEEN ? AND ? ORDER BY ts ASC LIMIT ?",
            (symbol, start_ts, end_ts, limit)).fetchall()
        return [dict(r) for r in rows]

    def symbols(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT symbol FROM bars ORDER BY symbol").fetchall()
        return [r["symbol"] for r in rows]

    # ---- 상태 ----
    def stats(self) -> dict:
        def count(table: str) -> int:
            try:
                return self._conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            except sqlite3.Error:
                return 0

        size = self.path.stat().st_size if (
            str(self.path) != ":memory:" and self.path.exists()) else 0
        return {
            "backend": self.backend,
            "connected": True,
            "path": str(self.path),
            "schema_version": self.schema_version,
            "size_bytes": size,
            "rows": {
                "kv": count("kv"),
                "events": count("events"),
                "predictions": count("predictions"),
                "facts": count("facts"),
                "bars": count("bars"),
            },
        }

    def reset_learning(self) -> dict:
        """★ 합성 데이터로 배운 것만 지우고, 실제 시세는 남깁니다.

        왜 필요한가
            합성 캔들 생성기에는 **의도적으로 사인파 사이클**이 들어 있습니다
            (docs/PATTERN_MINER.md). 그 위에서 학습한 모델은
            "되돌림이 잘 먹는다" 를 배웁니다. 실제 시장은 그렇지 않습니다.

            실데이터로 넘어갈 때 그 가중치를 그대로 두면, 에이전트는
            **없는 규칙을 이미 믿는 상태**로 시작합니다. 새로 배우기는 하지만
            느리고, 초기 판단이 오염됩니다.

        지우는 것       kv(모델 가중치·학습시간), events, predictions
        남기는 것       bars(실제 시세), facts(PIT 사실), 스키마

        시세를 남기는 이유: 그건 배운 게 아니라 받아온 사실이기 때문입니다.
        다시 받을 필요가 없습니다.
        """
        with self._lock:
            before = self.stats()["rows"]
            for table in ("kv", "events", "predictions"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()
            after = self.stats()["rows"]
        return {
            "cleared": {k: before[k] - after[k] for k in ("kv", "events", "predictions")},
            "kept": {"bars": after["bars"], "facts": after["facts"]},
            "note": ("학습 기록만 지웠습니다. 실제 시세와 PIT 사실은 그대로입니다."),
        }

    def vacuum(self) -> None:
        with self._lock:
            self._conn.execute("VACUUM")

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            finally:
                self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ------------------------------------------------------------------ 열기
def open_store(path: str | Path | None = None,
               backend: str = "sqlite") -> SqliteStore:
    """저장소를 엽니다.

    backend="postgres" 는 psycopg 가 필요합니다. 없으면 이유를 말하고
    **SQLite 로 조용히 내려가지 않습니다** — 사용자가 무엇을 쓰는지
    알아야 하기 때문입니다.
    """
    if backend == "postgres":
        raise PersistenceError(
            "PostgreSQL 백엔드는 psycopg 드라이버와 실행 중인 서버가 필요합니다. "
            "지금은 SQLite 를 쓰십시오 (backend='sqlite'). "
            "자세한 내용: docs/PERSISTENCE.md"
        )
    if backend != "sqlite":
        raise PersistenceError(f"모르는 백엔드입니다: {backend}")
    return SqliteStore(path or "data/airo.db")
