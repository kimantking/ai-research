"""Point-in-Time 저장소.

★ 이 프로젝트에서 가장 중요한 안전장치입니다.

문제
    일반 DB 는 '지금의 진실'만 저장합니다.
    기업이 나중에 실적을 정정하면 과거 값이 사라집니다.
    그 상태로 과거 시점을 분석하면, 그때는 알 수 없었던 정보를 보게 됩니다.
    백테스트 수익률은 환상적으로 나오고, 실전에서는 전부 잃습니다.

해결
    1) 모든 사실에 4개의 시간축을 붙입니다.
       event_time     사건이 실제 일어난 시각
       published_time 세상에 공개된 시각      ← 조회 필터의 기준
       received_time  우리가 가져온 시각
       effective_time 이 값이 유효한 것으로 간주되는 시각
    2) 정정되면 UPDATE 하지 않고 새 버전을 INSERT 합니다.
    3) 조회는 반드시 as_of 를 통해서만 합니다.
       as_of 이후에 공개된 것은 조회 자체가 불가능합니다.

    "미래를 보지 마세요"라고 부탁하는 방식이 아닙니다.
    볼 수 있는 통로가 없습니다.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


class PITError(RuntimeError):
    """시점 규칙을 어기려 할 때 발생합니다."""


@dataclass(frozen=True)
class Record:
    key: str                 # 예: "AAPL:2025Q4:revenue"
    value: Any
    event_time: int          # epoch seconds
    published_time: int      # ★ 조회 필터 기준
    received_time: int = 0
    effective_time: int = 0
    version: int = 1
    supersedes: int | None = None
    source_id: str = ""
    confidence: float = 1.0

    def __post_init__(self):
        if self.published_time < self.event_time:
            # 사건보다 먼저 공개될 수는 없습니다. 데이터 오류입니다.
            raise PITError(
                f"published_time({self.published_time}) 이 "
                f"event_time({self.event_time}) 보다 앞섭니다: {self.key}"
            )


class PITSeriesView:
    """as_of 시점까지만 보이는 시계열 뷰.

    슬라이싱해도 미래로는 넘어갈 수 없습니다.
    """

    __slots__ = ("_rows", "_as_of", "_cut")

    def __init__(self, rows: Sequence[tuple[int, Any]], as_of: int):
        # rows 는 (published_time, value) 오름차순
        self._rows = rows
        self._as_of = as_of
        times = [r[0] for r in rows]
        self._cut = bisect_right(times, as_of)

    def __len__(self) -> int:
        return self._cut

    def __iter__(self):
        for i in range(self._cut):
            yield self._rows[i][1]

    def __getitem__(self, item):
        if isinstance(item, slice):
            start, stop, step = item.indices(self._cut)
            return [self._rows[i][1] for i in range(start, stop, step)]
        if item < 0:
            item += self._cut
        if not 0 <= item < self._cut:
            raise IndexError(
                f"as_of={self._as_of} 시점에는 {item}번 데이터가 아직 존재하지 않습니다"
            )
        return self._rows[item][1]

    @property
    def as_of(self) -> int:
        return self._as_of

    def values(self) -> list[Any]:
        return [self._rows[i][1] for i in range(self._cut)]

    def hidden_count(self) -> int:
        """차단된(미래) 레코드 수 — 감사·테스트용."""
        return len(self._rows) - self._cut


class PITStore:
    """사실(fact)과 시계열을 시점 안전하게 보관합니다."""

    def __init__(self) -> None:
        self._facts: dict[str, list[Record]] = {}
        self._series: dict[str, list[tuple[int, Any]]] = {}
        self._series_sorted: dict[str, bool] = {}

    # ------------------------------------------------------------------ 쓰기
    def put_fact(self, rec: Record) -> None:
        bucket = self._facts.setdefault(rec.key, [])
        bucket.append(rec)
        bucket.sort(key=lambda r: (r.published_time, r.version))

    def revise_fact(self, key: str, value: Any, published_time: int,
                    event_time: int | None = None, source_id: str = "") -> Record:
        """정정 공시 — 덮어쓰지 않고 새 버전을 만듭니다."""
        prev = self._facts.get(key) or []
        version = (prev[-1].version + 1) if prev else 1
        rec = Record(
            key=key, value=value,
            event_time=event_time if event_time is not None else (
                prev[-1].event_time if prev else published_time
            ),
            published_time=published_time,
            version=version,
            supersedes=prev[-1].version if prev else None,
            source_id=source_id,
        )
        self.put_fact(rec)
        return rec

    def put_series(self, key: str, rows: Iterable[tuple[int, Any]]) -> None:
        bucket = self._series.setdefault(key, [])
        bucket.extend(rows)
        bucket.sort(key=lambda r: r[0])

    # ------------------------------------------------------------------ 읽기
    def get_fact(self, key: str, as_of: int) -> Record | None:
        """as_of 시점에 알 수 있었던 '가장 최신' 버전을 돌려줍니다."""
        bucket = self._facts.get(key)
        if not bucket:
            return None
        visible = [r for r in bucket if r.published_time <= as_of]
        return visible[-1] if visible else None

    def get_fact_history(self, key: str, as_of: int) -> list[Record]:
        bucket = self._facts.get(key) or []
        return [r for r in bucket if r.published_time <= as_of]

    def series(self, key: str, as_of: int) -> PITSeriesView:
        return PITSeriesView(self._series.get(key, []), as_of)

    # ------------------------------------------------------------------ 감사
    def audit(self, key: str, as_of: int) -> dict:
        """무엇이 보였고 무엇이 차단됐는지 — 나중에 재현하기 위한 기록."""
        facts = self._facts.get(key, [])
        blocked = [r for r in facts if r.published_time > as_of]
        return {
            "key": key,
            "as_of": as_of,
            "visible_versions": [r.version for r in facts if r.published_time <= as_of],
            "blocked_versions": [r.version for r in blocked],
            "blocked_count": len(blocked),
            "note": "blocked 항목은 as_of 시점에 존재하지 않았으므로 조회할 수 없습니다.",
        }
