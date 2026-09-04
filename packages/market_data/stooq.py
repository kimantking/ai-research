"""Stooq 일봉 CSV 공급자.

★ 왜 Stooq 인가
    - **API 키가 필요 없습니다** (사용자 승인·비용 없음 — §금지사항 준수)
    - 평범한 CSV 를 HTTPS 로 내려줍니다. 표준 라이브러리로 충분합니다.
    - 미국·유럽·한국 주요 종목을 다룹니다.

★ 한계 (숨기지 않습니다)
    - **비공식 엔드포인트입니다.** 예고 없이 형식이 바뀌거나 막힐 수 있습니다.
    - 조정 여부가 명시되지 않습니다. 우리는 `adjusted=False` 로 두고,
      분할 의심 구간을 품질 보고서에 표시합니다.
    - 과도한 호출은 차단될 수 있습니다. 요청 간 간격을 둡니다.
    - **약관을 직접 확인하고 쓰십시오.** 저는 확인해 드릴 수 없었습니다
      (이 개발 환경은 외부 접속이 막혀 있습니다).

★ 검증 상태
    파싱·정규화·품질검사: ✅ 저장된 실제 형식 응답으로 테스트 완료
    실제 네트워크 연결:   ❌ 미검증 (사용자 PC 에서 처음 확인됩니다)
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

from .base import (
    Bar,
    Bars,
    DataQualityReport,
    MarketDataError,
    ProviderResult,
    Transport,
    UrlTransport,
    check_quality,
)

BASE = "https://stooq.com/q/d/l/"


def _suffix_for(symbol: str) -> str:
    """Stooq 는 시장 접미사를 요구합니다 (aapl.us 처럼)."""
    s = symbol.strip().lower()
    if "." in s:
        return s
    if s.isdigit() and len(s) == 6:      # 한국 종목코드
        return f"{s}.kr"
    return f"{s}.us"


def _parse_date(text: str) -> int:
    d = datetime.strptime(text.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(d.timestamp())


class StooqProvider:
    id = "stooq"
    name = "Stooq (일봉 CSV)"
    requires_key = False
    terms_note = (
        "비공식 CSV 엔드포인트입니다. API 키·가입·비용이 없습니다. "
        "재배포·상업적 이용 전에 stooq.com 약관을 직접 확인하십시오."
    )
    verified = "파서 검증 완료 / 실제 네트워크 연결 미검증"

    def __init__(self, transport: Transport | None = None,
                 min_interval: float = 1.0, exchange: str | None = "XNYS"):
        self.transport = transport or UrlTransport("airo-research/1.0")
        self.min_interval = min_interval        # 예의 있는 호출 간격
        self.exchange = exchange
        self._last_call = 0.0

    # ------------------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def url_for(self, symbol: str, start: str | None = None,
                end: str | None = None) -> str:
        parts = [f"s={_suffix_for(symbol)}", "i=d"]
        if start:
            parts.append("d1=" + start.replace("-", ""))
        if end:
            parts.append("d2=" + end.replace("-", ""))
        return BASE + "?" + "&".join(parts)

    # ------------------------------------------------------------------
    def parse_csv(self, raw: bytes, symbol: str) -> Bars:
        """Stooq CSV 를 Bars 로 바꿉니다.

        기대 형식:
            Date,Open,High,Low,Close,Volume
            2024-01-02,187.15,188.44,183.89,185.64,82488700
        """
        text = raw.decode("utf-8-sig", errors="replace").strip()
        if not text:
            raise MarketDataError(f"{symbol}: 빈 응답")
        lines = [ln for ln in text.splitlines() if ln.strip()]

        # Stooq 는 없는 종목에 대해 이런 한 줄을 줍니다.
        if len(lines) == 1 or lines[0].lower().startswith("no data"):
            raise MarketDataError(
                f"{symbol}: 데이터가 없습니다 (심볼 또는 기간 확인). "
                f"응답: {lines[0][:80]}"
            )

        header = [h.strip().lower() for h in lines[0].split(",")]
        required = ["date", "open", "high", "low", "close"]
        missing = [c for c in required if c not in header]
        if missing:
            raise MarketDataError(
                f"{symbol}: CSV 형식이 예상과 다릅니다. 없는 컬럼: {missing}. "
                f"헤더: {lines[0][:120]}"
            )
        idx = {c: header.index(c) for c in header}
        has_volume = "volume" in idx

        bars: list[Bar] = []
        bad_rows = 0
        for ln in lines[1:]:
            cols = ln.split(",")
            if len(cols) < len(required):
                bad_rows += 1
                continue
            try:
                bars.append(Bar(
                    ts=_parse_date(cols[idx["date"]]),
                    open=float(cols[idx["open"]]),
                    high=float(cols[idx["high"]]),
                    low=float(cols[idx["low"]]),
                    close=float(cols[idx["close"]]),
                    volume=float(cols[idx["volume"]]) if has_volume and
                    cols[idx["volume"]].strip() not in ("", "-") else 0.0,
                ))
            except (ValueError, IndexError):
                bad_rows += 1
                continue

        if not bars:
            raise MarketDataError(f"{symbol}: 해석 가능한 행이 없습니다")

        bars.sort(key=lambda b: b.ts)
        out = Bars(
            symbol=symbol.upper(), bars=bars, source=self.id,
            adjusted=False,
            currency="KRW" if _suffix_for(symbol).endswith(".kr") else "USD",
        )
        out.notes.append(
            "조정 여부가 명시되지 않아 adjusted=False 로 둡니다. "
            "분할 의심 구간은 품질 보고서의 extreme_moves 를 보십시오."
        )
        if bad_rows:
            out.notes.append(f"해석 실패한 행 {bad_rows}개를 건너뛰었습니다")
        if not has_volume:
            out.notes.append("거래량 컬럼이 없어 0 으로 채웠습니다")
        return out

    # ------------------------------------------------------------------
    def fetch(self, symbol: str, start: str | None = None,
              end: str | None = None) -> ProviderResult:
        url = self.url_for(symbol, start, end)
        try:
            self._throttle()
            raw = self.transport.get(url)
            bars = self.parse_csv(raw, symbol)
        except MarketDataError as exc:
            return ProviderResult(ok=False, error=str(exc))
        except Exception as exc:                          # pragma: no cover
            return ProviderResult(ok=False, error=f"예상치 못한 오류: {exc}")

        quality = check_quality(bars, exchange=self.exchange)
        return ProviderResult(ok=True, bars=bars, quality=quality)

    # ------------------------------------------------------------------
    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "requires_key": self.requires_key,
            "cost": "무료",
            "verified": self.verified,
            "terms_note": self.terms_note,
        }
