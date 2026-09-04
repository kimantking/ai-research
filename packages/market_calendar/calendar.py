"""규칙 기반 거래일 캘린더 (표준 라이브러리만 사용).

★ 왜 필요한가

    백테스트에서 "T 종가 신호 → T+1 시가 체결" 이라고 말할 때,
    T+1 이 **다음 날**이면 틀립니다. **다음 거래일** 이어야 합니다.

    금요일 종가 신호는 월요일 시가에 체결됩니다.
    12월 24일(조기폐장) 신호는 12월 26일 시가에 체결됩니다.
    이걸 무시하면 "3일 뒤 수익률" 같은 값이 조용히 어긋나고,
    그 오차는 항상 같은 방향으로 쌓입니다.

★ 왜 직접 만들었나

    `exchange_calendars` 가 표준이지만 외부 의존성입니다.
    이 프로젝트는 "외부 패키지 없이도 돈다"를 지키고 있으므로,
    필요한 만큼만 규칙으로 구현했습니다.

★ 정직한 한계 (숨기지 않습니다)

    - NYSE: 1970~2035 는 **규칙으로 계산**합니다 (연방 공휴일 규칙 + 관측 규칙).
      대통령 서거 등 **1회성 특별 휴장**은 표로 넣었습니다. 표에 없는
      미래의 특별 휴장은 당연히 알 수 없습니다.
    - KRX: 신정·삼일절 같은 양력 공휴일은 규칙으로 계산하지만,
      **설날·추석·석가탄신일은 음력**이라 계산이 불가능합니다.
      2015~2035 표를 넣었고, 표 범위를 벗어나면 `known_range` 가
      False 를 돌려줍니다. **모른다고 말하지, 추측하지 않습니다.**
    - 임시 공휴일(대체휴일 지정 등)은 사후에 표를 갱신해야 합니다.

    `coverage()` 로 어디까지 신뢰할 수 있는지 항상 확인할 수 있습니다.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence

_DAY = 86_400


class CalendarError(RuntimeError):
    """캘린더가 답할 수 없는 질문을 받았을 때."""


# --------------------------------------------------------------------------
# 공통 날짜 계산기
# --------------------------------------------------------------------------
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """그 달의 n번째 특정 요일. weekday: 0=월 … 6=일."""
    d = date(year, month, 1)
    shift = (weekday - d.weekday()) % 7
    return d + timedelta(days=shift + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """그 달의 마지막 특정 요일."""
    if month == 12:
        d = date(year, 12, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """부활절 (Anonymous Gregorian algorithm). Good Friday 계산에 씁니다."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def _observed_us(d: date) -> date:
    """미국 관측 규칙: 토요일이면 전날 금요일, 일요일이면 다음날 월요일."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


# --------------------------------------------------------------------------
class ExchangeCalendar:
    """한 거래소의 휴장일/조기폐장을 아는 객체."""

    name = "GENERIC"
    tz_offset_minutes = 0          # 표준시 기준 UTC 오프셋 (참고용)
    first_year = 1970
    last_year = 2035
    weekend = (5, 6)               # 토, 일

    def __init__(self) -> None:
        self._holidays: dict[int, set[date]] = {}
        self._early: dict[int, dict[date, str]] = {}

    # ---- 하위 클래스가 구현 ----
    def _build_year(self, year: int) -> tuple[set[date], dict[date, str]]:
        raise NotImplementedError

    def known_range(self) -> tuple[int, int]:
        return (self.first_year, self.last_year)

    # ---- 공통 ----
    def _year(self, year: int) -> tuple[set[date], dict[date, str]]:
        if year not in self._holidays:
            hol, early = self._build_year(year)
            self._holidays[year] = hol
            self._early[year] = early
        return self._holidays[year], self._early[year]

    def _check_year(self, d: date) -> None:
        lo, hi = self.known_range()
        if not (lo <= d.year <= hi):
            raise CalendarError(
                f"{self.name} 캘린더는 {lo}~{hi} 만 압니다 "
                f"(요청: {d.isoformat()}). 추측하지 않습니다."
            )

    def is_holiday(self, d: date) -> bool:
        self._check_year(d)
        hol, _ = self._year(d.year)
        return d in hol

    def is_weekend(self, d: date) -> bool:
        return d.weekday() in self.weekend

    def is_session(self, d: date) -> bool:
        """그 날 정규장이 열리는가."""
        if self.is_weekend(d):
            return False
        return not self.is_holiday(d)

    def is_early_close(self, d: date) -> bool:
        self._check_year(d)
        _, early = self._year(d.year)
        return d in early and self.is_session(d)

    def early_close_reason(self, d: date) -> str | None:
        self._check_year(d)
        _, early = self._year(d.year)
        return early.get(d) if self.is_session(d) else None

    # ---- 이동 ----
    def next_session(self, d: date, n: int = 1) -> date:
        """d **이후** n번째 거래일. d 자체는 세지 않습니다."""
        if n < 1:
            raise CalendarError("n 은 1 이상이어야 합니다")
        cur = d
        for _ in range(n):
            cur += timedelta(days=1)
            guard = 0
            while not self.is_session(cur):
                cur += timedelta(days=1)
                guard += 1
                if guard > 30:
                    raise CalendarError(f"{self.name}: 30일 연속 휴장? 데이터 오류")
        return cur

    def previous_session(self, d: date, n: int = 1) -> date:
        if n < 1:
            raise CalendarError("n 은 1 이상이어야 합니다")
        cur = d
        for _ in range(n):
            cur -= timedelta(days=1)
            guard = 0
            while not self.is_session(cur):
                cur -= timedelta(days=1)
                guard += 1
                if guard > 30:
                    raise CalendarError(f"{self.name}: 30일 연속 휴장? 데이터 오류")
        return cur

    def sessions_between(self, start: date, end: date) -> list[date]:
        """[start, end] 안의 거래일 목록 (양끝 포함)."""
        if end < start:
            return []
        self._check_year(start)
        self._check_year(end)
        out: list[date] = []
        cur = start
        while cur <= end:
            if self.is_session(cur):
                out.append(cur)
            cur += timedelta(days=1)
        return out

    def session_count(self, start: date, end: date) -> int:
        return len(self.sessions_between(start, end))

    def align(self, d: date, direction: str = "forward") -> date:
        """휴장일이면 가장 가까운 거래일로 밀어줍니다."""
        if self.is_session(d):
            return d
        return (self.next_session(d) if direction == "forward"
                else self.previous_session(d))

    # ---- epoch 편의 함수 ----
    @staticmethod
    def to_date(ts: int) -> date:
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()

    @staticmethod
    def to_ts(d: date) -> int:
        return int(datetime(d.year, d.month, d.day,
                            tzinfo=timezone.utc).timestamp())

    def next_session_ts(self, ts: int, n: int = 1) -> int:
        return self.to_ts(self.next_session(self.to_date(ts), n))

    def is_session_ts(self, ts: int) -> bool:
        return self.is_session(self.to_date(ts))

    # ---- 자기 진단 ----
    def coverage(self) -> dict:
        lo, hi = self.known_range()
        return {
            "exchange": self.name,
            "known_from": lo,
            "known_to": hi,
            "method": self.coverage_method,
            "caveats": self.caveats,
        }

    coverage_method = "rule-based"
    caveats: list[str] = []


# --------------------------------------------------------------------------
# NYSE / NASDAQ
# --------------------------------------------------------------------------
# 1회성 특별 휴장 (규칙으로 계산 불가능한 사건들)
_NYSE_SPECIAL_CLOSURES: dict[date, str] = {
    date(2001, 9, 11): "9/11 테러",
    date(2001, 9, 12): "9/11 테러",
    date(2001, 9, 13): "9/11 테러",
    date(2001, 9, 14): "9/11 테러",
    date(2004, 6, 11): "레이건 전 대통령 장례",
    date(2007, 1, 2): "포드 전 대통령 장례",
    date(2012, 10, 29): "허리케인 샌디",
    date(2012, 10, 30): "허리케인 샌디",
    date(2018, 12, 5): "부시 전 대통령 장례",
    date(2025, 1, 9): "카터 전 대통령 장례",
}


class NYSE(ExchangeCalendar):
    """뉴욕증권거래소 / 나스닥 (정규장 기준)."""

    name = "XNYS"
    tz_offset_minutes = -300      # EST
    first_year = 1970
    last_year = 2035
    coverage_method = "연방 공휴일 규칙 + 관측 규칙 + 특별 휴장 표"
    caveats = [
        "표에 없는 미래의 1회성 특별 휴장(장례·재해)은 알 수 없습니다.",
        "조기폐장(13:00 ET)은 날짜만 표시하고 시각은 다루지 않습니다.",
    ]

    def _build_year(self, year: int):
        hol: set[date] = set()

        # 신정
        hol.add(_observed_us(date(year, 1, 1)))
        # 마틴 루터 킹 데이 (1998~, 1월 셋째 월요일)
        if year >= 1998:
            hol.add(_nth_weekday(year, 1, 0, 3))
        # 워싱턴 탄생일 (1971~, 2월 셋째 월요일)
        if year >= 1971:
            hol.add(_nth_weekday(year, 2, 0, 3))
        else:
            hol.add(_observed_us(date(year, 2, 22)))
        # 성금요일 (부활절 전 금요일) — NYSE 는 휴장
        hol.add(_easter(year) - timedelta(days=2))
        # 메모리얼 데이 (1971~, 5월 마지막 월요일)
        if year >= 1971:
            hol.add(_last_weekday(year, 5, 0))
        else:
            hol.add(_observed_us(date(year, 5, 30)))
        # 준틴스 (2022~, 6월 19일)
        if year >= 2022:
            hol.add(_observed_us(date(year, 6, 19)))
        # 독립기념일
        hol.add(_observed_us(date(year, 7, 4)))
        # 노동절 (9월 첫째 월요일)
        hol.add(_nth_weekday(year, 9, 0, 1))
        # 추수감사절 (11월 넷째 목요일)
        thanksgiving = _nth_weekday(year, 11, 3, 4)
        hol.add(thanksgiving)
        # 성탄절
        hol.add(_observed_us(date(year, 12, 25)))

        for d, _why in _NYSE_SPECIAL_CLOSURES.items():
            if d.year == year:
                hol.add(d)

        # ---- 조기폐장 (13:00 ET) ----
        early: dict[date, str] = {}
        # 추수감사절 다음날
        early[thanksgiving + timedelta(days=1)] = "추수감사절 다음날"
        # 성탄 전야 (평일이고 성탄절이 화~금일 때)
        eve = date(year, 12, 24)
        if eve.weekday() < 5:
            early[eve] = "성탄 전야"
        # 독립기념일 전날 (7월 3일이 평일이면)
        jul3 = date(year, 7, 3)
        if jul3.weekday() < 5 and date(year, 7, 4).weekday() < 5:
            early[jul3] = "독립기념일 전날"

        early = {d: why for d, why in early.items() if d not in hol}
        return hol, early


# --------------------------------------------------------------------------
# KRX (한국거래소)
# --------------------------------------------------------------------------
# 음력 기반 공휴일은 계산이 불가능하므로 표로 관리합니다.
# (설날 연휴 3일 / 추석 연휴 3일 / 석가탄신일)
_KRX_LUNAR: dict[int, list[tuple[int, int]]] = {
    2015: [(2, 18), (2, 19), (2, 20), (5, 25), (9, 26), (9, 27), (9, 28), (9, 29)],
    2016: [(2, 7), (2, 8), (2, 9), (2, 10), (5, 14), (9, 14), (9, 15), (9, 16)],
    2017: [(1, 27), (1, 28), (1, 29), (1, 30), (5, 3), (10, 3), (10, 4), (10, 5), (10, 6)],
    2018: [(2, 15), (2, 16), (2, 17), (5, 22), (9, 23), (9, 24), (9, 25), (9, 26)],
    2019: [(2, 4), (2, 5), (2, 6), (5, 12), (9, 12), (9, 13), (9, 14)],
    2020: [(1, 24), (1, 25), (1, 26), (1, 27), (4, 30), (9, 30), (10, 1), (10, 2)],
    2021: [(2, 11), (2, 12), (2, 13), (5, 19), (9, 20), (9, 21), (9, 22)],
    2022: [(1, 31), (2, 1), (2, 2), (5, 8), (9, 9), (9, 10), (9, 11), (9, 12)],
    2023: [(1, 21), (1, 22), (1, 23), (1, 24), (5, 27), (5, 29), (9, 28), (9, 29), (9, 30)],
    2024: [(2, 9), (2, 10), (2, 11), (2, 12), (5, 15), (9, 16), (9, 17), (9, 18)],
    2025: [(1, 28), (1, 29), (1, 30), (5, 5), (5, 6), (10, 5), (10, 6), (10, 7), (10, 8)],
    2026: [(2, 16), (2, 17), (2, 18), (5, 24), (5, 25), (9, 24), (9, 25), (9, 26)],
    2027: [(2, 6), (2, 7), (2, 8), (2, 9), (5, 13), (9, 14), (9, 15), (9, 16)],
    2028: [(1, 26), (1, 27), (1, 28), (5, 2), (10, 2), (10, 3), (10, 4)],
    2029: [(2, 12), (2, 13), (2, 14), (5, 20), (9, 21), (9, 22), (9, 23)],
    2030: [(2, 2), (2, 3), (2, 4), (2, 5), (5, 9), (9, 11), (9, 12), (9, 13)],
    2031: [(1, 22), (1, 23), (1, 24), (5, 28), (9, 30), (10, 1), (10, 2)],
    2032: [(2, 10), (2, 11), (2, 12), (5, 16), (9, 18), (9, 19), (9, 20)],
    2033: [(1, 30), (1, 31), (2, 1), (2, 2), (5, 6), (9, 7), (9, 8), (9, 9)],
    2034: [(2, 18), (2, 19), (2, 20), (5, 25), (9, 26), (9, 27), (9, 28)],
    2035: [(2, 7), (2, 8), (2, 9), (5, 15), (9, 15), (9, 16), (9, 17)],
}

# 임시공휴일 / 대체공휴일 등 규칙 밖의 휴장 (확정된 것만)
_KRX_EXTRA: dict[date, str] = {
    date(2015, 8, 14): "광복 70주년 임시공휴일",
    date(2016, 5, 6): "임시공휴일",
    date(2017, 5, 9): "대통령 선거",
    date(2017, 10, 2): "임시공휴일",
    date(2020, 4, 15): "국회의원 선거",
    date(2020, 8, 17): "임시공휴일",
    date(2022, 3, 9): "대통령 선거",
    date(2022, 6, 1): "지방선거",
    date(2023, 10, 2): "임시공휴일",
    date(2024, 4, 10): "국회의원 선거",
    date(2024, 10, 1): "국군의날 임시공휴일",
    date(2025, 6, 3): "대통령 선거",
}


class KRX(ExchangeCalendar):
    """한국거래소.

    ⚠️ 음력 공휴일 때문에 표 범위(2015~2035) 밖은 답하지 않습니다.
    """

    name = "XKRX"
    tz_offset_minutes = 540
    first_year = 2015
    last_year = 2035
    coverage_method = "양력 공휴일 규칙 + 음력 공휴일 표 + 임시공휴일 표"
    caveats = [
        "설날·추석·석가탄신일은 음력이라 계산 불가 — 2015~2035 표를 사용합니다.",
        "향후 지정될 임시공휴일·대체공휴일은 표를 갱신해야 반영됩니다.",
        "연말 폐장일(12/31 휴장)을 반영합니다.",
    ]

    def _build_year(self, year: int):
        hol: set[date] = set()
        fixed = [
            (1, 1, "신정"),
            (3, 1, "삼일절"),
            (5, 1, "근로자의날"),
            (5, 5, "어린이날"),
            (6, 6, "현충일"),
            (8, 15, "광복절"),
            (10, 3, "개천절"),
            (10, 9, "한글날"),
            (12, 25, "성탄절"),
        ]
        for m, d, _why in fixed:
            hol.add(date(year, m, d))

        for m, d in _KRX_LUNAR.get(year, []):
            hol.add(date(year, m, d))

        for d, _why in _KRX_EXTRA.items():
            if d.year == year:
                hol.add(d)

        # 연말 폐장일: 12월 31일. 주말이면 직전 영업일.
        last = date(year, 12, 31)
        while last.weekday() in self.weekend:
            last -= timedelta(days=1)
        hol.add(last)

        return hol, {}


# --------------------------------------------------------------------------
_REGISTRY: dict[str, ExchangeCalendar] = {}


def get_calendar(name: str) -> ExchangeCalendar:
    """거래소 캘린더를 가져옵니다. 같은 이름은 같은 객체(캐시 공유)."""
    key = name.upper().strip()
    alias = {
        "NYSE": "XNYS", "NASDAQ": "XNYS", "XNAS": "XNYS", "US": "XNYS",
        "KRX": "XKRX", "KOSPI": "XKRX", "KOSDAQ": "XKRX", "KR": "XKRX",
    }
    key = alias.get(key, key)
    if key not in _REGISTRY:
        cls = {"XNYS": NYSE, "XKRX": KRX}.get(key)
        if cls is None:
            raise CalendarError(
                f"모르는 거래소입니다: {name}. "
                f"사용 가능: {', '.join(sorted(list_calendars()))}"
            )
        _REGISTRY[key] = cls()
    return _REGISTRY[key]


def list_calendars() -> list[str]:
    return ["XNYS", "XKRX"]


# 이름 호환 (문서에서 MarketCalendar 로 부르기도 합니다)
MarketCalendar = ExchangeCalendar
