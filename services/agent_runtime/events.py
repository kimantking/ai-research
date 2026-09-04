"""이벤트 버스 — 백엔드에서 일어난 일을 프론트로 실시간 전달합니다.

★ 원칙 (§44 Fake Status 금지)
   프론트엔드는 상태를 지어내지 않습니다.
   여기서 이벤트가 나가지 않으면 캐릭터는 움직이지 않습니다.
   모든 이벤트에는 is_mock 플래그가 강제로 붙습니다.

★ 두 종류의 구독자를 지원합니다
   - 스레드 구독자 (표준 라이브러리 서버용): queue.Queue
   - asyncio 구독자 (FastAPI 용): asyncio.Queue
   두 서버 구현이 같은 버스를 쓰므로 동작이 갈릴 일이 없습니다.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    def __init__(self, history_size: int = 500, max_pending: int = 500):
        self._lock = threading.RLock()
        self._thread_subs: set[queue.Queue] = set()
        self._async_subs: list[tuple[asyncio.Queue, asyncio.AbstractEventLoop | None]] = []
        self.history: deque[dict] = deque(maxlen=history_size)
        self.total_emitted = 0
        self.max_pending = max_pending

    # ------------------------------------------------------------------ 구독
    def subscribe_thread(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self.max_pending)
        with self._lock:
            self._thread_subs.add(q)
        return q

    def unsubscribe_thread(self, q: queue.Queue) -> None:
        with self._lock:
            self._thread_subs.discard(q)

    def subscribe_async(
        self, loop: asyncio.AbstractEventLoop | None = None
    ) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self.max_pending)
        with self._lock:
            self._async_subs.append((q, loop))
        return q

    def unsubscribe_async(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._async_subs = [(x, l) for (x, l) in self._async_subs if x is not q]

    # 하위 호환 (기존 이름)
    subscribe = subscribe_async
    unsubscribe = unsubscribe_async

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._thread_subs) + len(self._async_subs)

    # ------------------------------------------------------------------ 발행
    def emit(self, type_: str, *, is_mock: bool, **payload: Any) -> dict:
        event = {"type": type_, "ts": _now(), "is_mock": is_mock, **payload}
        with self._lock:
            self.history.append(event)
            self.total_emitted += 1
            thread_subs = list(self._thread_subs)
            async_subs = list(self._async_subs)

        # 느린 구독자 하나 때문에 엔진 전체가 멈추면 안 됩니다.
        # 큐가 가득 차면 가장 오래된 것을 버리고 최신을 넣습니다.
        for q in thread_subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    self.unsubscribe_thread(q)

        for q, loop in async_subs:
            try:
                if loop is not None and not loop.is_closed():
                    loop.call_soon_threadsafe(self._async_put, q, event)
                else:
                    self._async_put(q, event)
            except RuntimeError:
                self.unsubscribe_async(q)

        return event

    # ------------------------------------------------------------------
    @staticmethod
    def _async_put(q: asyncio.Queue, event: dict) -> None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.put_nowait(event)
            except Exception:
                pass

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self.history)[-n:]
