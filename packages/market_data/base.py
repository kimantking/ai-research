"""공급자 공통 계약.

★ 왜 transport 를 분리했나

    `urllib.request.urlopen` 을 함수 안에서 직접 부르면, 그 함수는
    인터넷 없이 테스트할 수 없습니다. 그러면 파서 버그가 사용자 PC 에서
    처음 발견됩니다.

    Transport 를 인자로 받으면, 테스트에서는 저장해 둔 실제 응답을
    그대로 넣어줄 수 있습니다. **파싱·정규화·품질검사 로직은 100% 검증**되고,
    검증되지 않은 채 남는 것은 "실제로 네트워크가 연결되는가" 하나뿐입니다.
    그 하나는 정직하게 '미검증'이라고 표시합니다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, Sequence

MAX_BYTES = 12 * 1024 * 1024        # 12MB. 이보다 크면 뭔가 잘못된 것입니다.
DEFAULT_TIMEOUT = 20.0


class MarketDataError(RuntimeError):
    """데이터를 가져오지 못했거나 믿을 수 없을 때."""


# ------------------------------------------------------------------ 자료구조
@dataclass(frozen=True)
class Bar:
    ts: int          # epoch seconds (해당 거래일 00:00 UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self) -> dict:
        return {"ts": self.ts, "o": self.open, "h": self.high,
                "l": self.low, "c": self.close, "v": self.volume}


@dataclass
class Bars:
    symbol: str
    bars: list[Bar] = field(default_factory=list)
    source: str = ""
    adjusted: bool = False
    fetched_at: int = field(default_factory=lambda: int(time.time()))
    currency: str = "USD"
    notes: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self):
        return iter(self.bars)

    @property
    def first_ts(self) -> int | None:
        return self.bars[0].ts if self.bars else None

    @property
    def last_ts(self) -> int | None:
        return self.bars[-1].ts if self.bars else None

    def to_dicts(self) -> list[dict]:
        return [b.as_dict() for b in self.bars]

    def summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "adjusted": self.adjusted,
            "bars": len(self.bars),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "currency": self.currency,
            "notes": self.notes,
        }


@dataclass
class DataQualityReport:
    """가져온 데이터를 믿어도 되는지 스스로 점검한 결과.

    ★ 이 보고서가 없으면 조용히 잘못된 데이터로 백테스트를 돌리게 됩니다.
    """
    symbol: str
    bars: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    non_positive_prices: int = 0
    inconsistent_ohlc: int = 0       # high < low, close 가 [low, high] 밖 등
    zero_volume_days: int = 0
    extreme_moves: list[str] = field(default_factory=list)   # 하루 ±50% 이상
    gaps: int = 0                    # 빠진 거래일 수
    non_session_bars: int = 0        # 휴장일에 있는 봉
    calendar_checked: bool = False
    problems: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """치명적 문제가 없는가. 경고(gap 등)만으로는 막지 않습니다."""
        return not (self.duplicates or self.out_of_order
                    or self.non_positive_prices or self.inconsistent_ohlc)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bars": self.bars,
            "usable": self.usable,
            "duplicates": self.duplicates,
            "out_of_order": self.out_of_order,
            "non_positive_prices": self.non_positive_prices,
            "inconsistent_ohlc": self.inconsistent_ohlc,
            "zero_volume_days": self.zero_volume_days,
            "extreme_moves": self.extreme_moves[:10],
            "missing_sessions": self.gaps,
            "non_session_bars": self.non_session_bars,
            "calendar_checked": self.calendar_checked,
            "problems": self.problems,
        }


@dataclass
class ProviderResult:
    ok: bool
    bars: Bars | None = None
    quality: DataQualityReport | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "bars": self.bars.summary() if self.bars else None,
            "quality": self.quality.to_dict() if self.quality else None,
        }


# ------------------------------------------------------------------ transport
class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str] | None = None,
            timeout: float = DEFAULT_TIMEOUT) -> bytes: ...


class UrlTransport:
    """표준 라이브러리 urllib 기반 HTTP GET.

    - HTTPS 만 허용합니다 (평문 HTTP 로 시세를 받지 않습니다).
    - 응답 크기 상한을 둡니다.
    - 리다이렉트를 따라가되 스킴이 바뀌면 거부합니다.
    """

    def __init__(self, user_agent: str = "airo-research/1.0"):
        self.user_agent = user_agent
        self.last_status: int | None = None

    def get(self, url: str, headers: dict[str, str] | None = None,
            timeout: float = DEFAULT_TIMEOUT) -> bytes:
        import urllib.error
        import urllib.request

        if not url.lower().startswith("https://"):
            raise MarketDataError(f"HTTPS 가 아닌 주소는 거부합니다: {url[:80]}")

        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", self.user_agent)
        req.add_header("Accept-Encoding", "identity")
        for k, v in (headers or {}).items():
            req.add_header(k, v)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self.last_status = resp.status
                if not resp.url.lower().startswith("https://"):
                    raise MarketDataError("리다이렉트가 HTTPS 를 벗어났습니다")
                data = resp.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            self.last_status = exc.code
            raise MarketDataError(f"HTTP {exc.code} — {url[:80]}") from exc
        except urllib.error.URLError as exc:
            raise MarketDataError(f"네트워크 오류: {exc.reason}") from exc
        except TimeoutError as exc:
            raise MarketDataError(f"시간 초과 ({timeout}s)") from exc

        if len(data) > MAX_BYTES:
            raise MarketDataError(f"응답이 너무 큽니다 (> {MAX_BYTES} bytes)")
        return data


# ------------------------------------------------------------------ 공급자
class Provider(Protocol):
    id: str
    name: str
    requires_key: bool
    terms_note: str

    def fetch(self, symbol: str, start: str | None = None,
              end: str | None = None) -> ProviderResult: ...


# ------------------------------------------------------------------ 품질검사
def check_quality(bars: Bars, exchange: str | None = None,
                  extreme_move: float = 0.5) -> DataQualityReport:
    """가져온 데이터를 스스로 검사합니다.

    여기서 걸러내지 못하면 백테스트가 쓰레기 데이터 위에서 돌아가고,
    그 결과는 **그럴듯해 보입니다.** 그래서 조용한 오류가 가장 위험합니다.
    """
    rep = DataQualityReport(symbol=bars.symbol, bars=len(bars))
    seen: set[int] = set()
    prev_ts: int | None = None
    prev_close: float | None = None

    for b in bars:
        if b.ts in seen:
            rep.duplicates += 1
        seen.add(b.ts)

        if prev_ts is not None and b.ts <= prev_ts:
            rep.out_of_order += 1
        prev_ts = b.ts

        if min(b.open, b.high, b.low, b.close) <= 0:
            rep.non_positive_prices += 1
        elif not (b.low <= b.open <= b.high and b.low <= b.close <= b.high
                  and b.low <= b.high):
            rep.inconsistent_ohlc += 1

        if b.volume == 0:
            rep.zero_volume_days += 1

        if prev_close and prev_close > 0:
            move = abs(b.close - prev_close) / prev_close
            # ★ '>' 가 아니라 '>=' 입니다.
            #   2:1 분할은 정확히 -50.0% 입니다. 가장 흔한 경우가
            #   경계에 딱 걸려 빠져나가면 검사의 의미가 없습니다.
            if move >= extreme_move - 1e-9:
                rep.extreme_moves.append(
                    f"ts={b.ts} {move:+.1%} (분할·병합 미조정 가능성)")
        prev_close = b.close

    if rep.duplicates:
        rep.problems.append(f"중복된 날짜 {rep.duplicates}건")
    if rep.out_of_order:
        rep.problems.append(f"시간 역순 {rep.out_of_order}건 — 정렬이 깨졌습니다")
    if rep.non_positive_prices:
        rep.problems.append(f"0 이하 가격 {rep.non_positive_prices}건")
    if rep.inconsistent_ohlc:
        rep.problems.append(
            f"OHLC 모순 {rep.inconsistent_ohlc}건 (high<low 등) — 데이터 오류")
    if rep.extreme_moves:
        rep.problems.append(
            f"하루 ±{extreme_move:.0%} 이상 변동 {len(rep.extreme_moves)}건 — "
            "주식분할이 반영되지 않았을 수 있습니다")

    if exchange:
        try:
            from packages.market_calendar import SessionClock
            clock = SessionClock.from_timestamps([b.ts for b in bars], exchange)
            summary = clock.summary()
            rep.calendar_checked = True
            rep.non_session_bars = summary["non_session_bars"]
            rep.gaps = summary["missing_sessions"]
            if rep.non_session_bars:
                rep.problems.append(
                    f"휴장일에 봉이 {rep.non_session_bars}개 있습니다")
            if rep.gaps:
                rep.problems.append(
                    f"거래일인데 데이터가 없는 날이 {rep.gaps}일 있습니다")
        except Exception as exc:                          # pragma: no cover
            rep.problems.append(f"캘린더 검사 실패: {exc}")

    return rep
