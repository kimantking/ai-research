"""거래 세션 시계.

백테스트·예측 저널이 "N 거래일 뒤"를 정확히 계산하도록 돕습니다.
달력 날짜가 아니라 **세션 인덱스**로 생각하게 만드는 것이 목적입니다.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from .calendar import CalendarError, ExchangeCalendar, get_calendar


class SessionClock:
    """어떤 시계열의 봉 인덱스를 실제 거래일에 묶어줍니다.

    사용법
        clock = SessionClock.from_timestamps(ts_list, "XNYS")
        clock.horizon_ts(i, 5)      # i번째 봉에서 5 거래일 뒤의 timestamp
        clock.is_aligned()          # 시계열이 실제 거래일과 맞는가
    """

    def __init__(self, dates: Sequence[date], calendar: ExchangeCalendar):
        self.dates = list(dates)
        self.calendar = calendar
        self._index = {d: i for i, d in enumerate(self.dates)}

    # ---- 생성 ----
    @classmethod
    def from_timestamps(cls, timestamps: Sequence[int],
                        exchange: str = "XNYS") -> "SessionClock":
        cal = get_calendar(exchange)
        return cls([ExchangeCalendar.to_date(t) for t in timestamps], cal)

    # ---- 검사 ----
    def is_aligned(self) -> bool:
        """시계열의 모든 날짜가 실제 거래일인가."""
        try:
            return all(self.calendar.is_session(d) for d in self.dates)
        except CalendarError:
            return False

    def non_session_days(self) -> list[str]:
        """거래일이 아닌데 데이터가 있는 날 (합성 데이터면 잔뜩 나옵니다)."""
        out = []
        for d in self.dates:
            try:
                if not self.calendar.is_session(d):
                    out.append(d.isoformat())
            except CalendarError:
                out.append(d.isoformat() + " (범위 밖)")
        return out

    def missing_sessions(self) -> list[str]:
        """거래일인데 데이터가 없는 날 (데이터 결손 탐지)."""
        if not self.dates:
            return []
        try:
            expected = self.calendar.sessions_between(self.dates[0], self.dates[-1])
        except CalendarError:
            return []
        have = set(self.dates)
        return [d.isoformat() for d in expected if d not in have]

    # ---- 이동 ----
    def horizon_index(self, i: int, horizon: int) -> int | None:
        """i번째 봉에서 horizon 거래일 뒤의 **봉 인덱스**.

        시계열이 거래일과 정렬돼 있으면 그냥 i + horizon 입니다.
        정렬돼 있지 않으면(합성 데이터 등) None 을 돌려주고,
        호출한 쪽이 '거래일 기준이 아님' 을 알 수 있게 합니다.
        """
        j = i + horizon
        if 0 <= j < len(self.dates):
            return j
        return None

    def horizon_date(self, i: int, horizon: int) -> date | None:
        """i번째 봉의 날짜에서 horizon **거래일** 뒤의 실제 날짜."""
        if not (0 <= i < len(self.dates)):
            return None
        try:
            return self.calendar.next_session(self.dates[i], horizon)
        except CalendarError:
            return None

    def index_of(self, d: date) -> int | None:
        return self._index.get(d)

    def summary(self) -> dict:
        non = self.non_session_days()
        missing = self.missing_sessions()
        return {
            "exchange": self.calendar.name,
            "bars": len(self.dates),
            "aligned_to_sessions": not non,
            "non_session_bars": len(non),
            "missing_sessions": len(missing),
            "first": self.dates[0].isoformat() if self.dates else None,
            "last": self.dates[-1].isoformat() if self.dates else None,
            "note": (
                "거래일과 정렬되지 않았습니다 — 합성 데이터이거나 결손이 있습니다."
                if non else "실제 거래일과 정렬되어 있습니다."
            ),
        }
