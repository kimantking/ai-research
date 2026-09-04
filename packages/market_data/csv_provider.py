"""사용자가 직접 넣은 CSV 파일 공급자.

★ 왜 필요한가

    인터넷 공급자는 언제든 막힐 수 있고, 약관도 제각각입니다.
    증권사에서 내려받은 CSV 를 `data/market/` 에 넣기만 하면
    **아무 외부 서비스 없이** 실제 데이터로 학습·백테스트가 됩니다.

    이게 가장 확실한 경로입니다. 약관 문제도 없고, 네트워크도 필요 없습니다.

★ 받아들이는 형식

    컬럼 이름은 대소문자·공백을 무시하고 아래 별칭을 모두 인식합니다.

        날짜   date / Date / 일자 / timestamp / time
        시가   open / Open / 시가
        고가   high / 고가
        저가   low  / 저가
        종가   close / Close / 종가 / adj close / Adj Close
        거래량 volume / Volume / 거래량        (없으면 0)

    날짜 형식: 2024-01-02 / 2024/01/02 / 20240102 / 2024.01.02
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from .base import Bar, Bars, MarketDataError, ProviderResult, check_quality

_ALIASES = {
    "date": {"date", "일자", "날짜", "timestamp", "time", "datetime", "기준일자"},
    "open": {"open", "시가", "openprice", "o"},
    "high": {"high", "고가", "highprice", "h"},
    "low": {"low", "저가", "lowprice", "l"},
    "close": {"close", "종가", "closeprice", "c", "adjclose", "adjustedclose",
              "adj close", "수정종가"},
    "volume": {"volume", "거래량", "vol", "v", "거래대금"},
}

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d",
                 "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y")


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "").replace(" ", "")


def _map_columns(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    normalized = [_norm(h) for h in header]
    for field, aliases in _ALIASES.items():
        alias_norm = {_norm(a) for a in aliases}
        for i, h in enumerate(normalized):
            if h in alias_norm:
                mapping[field] = i
                break
    return mapping


def _parse_date(text: str) -> int:
    t = text.strip().strip('"')
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(t, fmt).replace(tzinfo=timezone.utc)
            return int(datetime(d.year, d.month, d.day,
                                tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise MarketDataError(f"날짜 형식을 알 수 없습니다: {text[:30]}")


def _num(text: str) -> float:
    t = text.strip().strip('"').replace(",", "")
    if t in ("", "-", "N/A", "null", "None"):
        return 0.0
    return float(t)


class CsvFileProvider:
    id = "csv_file"
    name = "CSV 파일 (직접 넣은 데이터)"
    requires_key = False
    terms_note = (
        "사용자가 직접 준비한 파일입니다. 외부 서비스를 거치지 않으므로 "
        "약관·비용 문제가 없습니다. 다만 데이터의 정확성은 원본에 달려 있습니다."
    )
    verified = "파서·품질검사 검증 완료"

    def __init__(self, directory: str | Path = "data/market",
                 exchange: str | None = "XNYS"):
        self.directory = Path(directory)
        self.exchange = exchange

    # ------------------------------------------------------------------
    def available(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(p.stem.upper() for p in self.directory.glob("*.csv"))

    def parse_text(self, text: str, symbol: str) -> Bars:
        reader = csv.reader(io.StringIO(text))
        rows = [r for r in reader if r and any(c.strip() for c in r)]
        if len(rows) < 2:
            raise MarketDataError(f"{symbol}: 데이터 행이 없습니다")

        mapping = _map_columns(rows[0])
        needed = ["date", "open", "high", "low", "close"]
        missing = [c for c in needed if c not in mapping]
        if missing:
            raise MarketDataError(
                f"{symbol}: 필요한 컬럼을 찾지 못했습니다: {missing}. "
                f"파일의 첫 줄: {','.join(rows[0])[:120]}"
            )

        bars: list[Bar] = []
        skipped = 0
        for r in rows[1:]:
            try:
                bars.append(Bar(
                    ts=_parse_date(r[mapping["date"]]),
                    open=_num(r[mapping["open"]]),
                    high=_num(r[mapping["high"]]),
                    low=_num(r[mapping["low"]]),
                    close=_num(r[mapping["close"]]),
                    volume=_num(r[mapping["volume"]]) if "volume" in mapping else 0.0,
                ))
            except (MarketDataError, ValueError, IndexError):
                skipped += 1
                continue

        if not bars:
            raise MarketDataError(f"{symbol}: 해석 가능한 행이 없습니다")

        bars.sort(key=lambda b: b.ts)
        out = Bars(symbol=symbol.upper(), bars=bars, source=self.id,
                   adjusted=False)
        if skipped:
            out.notes.append(f"해석 실패한 행 {skipped}개를 건너뛰었습니다")
        out.notes.append(
            "이 파일이 조정주가인지 원주가인지는 파일만 보고 알 수 없습니다. "
            "adjusted=False 로 두었습니다."
        )
        return out

    # ------------------------------------------------------------------
    def fetch(self, symbol: str, start: str | None = None,
              end: str | None = None) -> ProviderResult:
        path = self.directory / f"{symbol.upper()}.csv"
        if not path.exists():
            alt = self.directory / f"{symbol.lower()}.csv"
            path = alt if alt.exists() else path
        if not path.exists():
            return ProviderResult(
                ok=False,
                error=(f"{path} 가 없습니다. "
                       f"CSV 를 {self.directory}/ 에 넣어주세요 "
                       f"(파일명 = 종목코드, 예: NVDA.csv)"),
            )
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            bars = self.parse_text(text, symbol)
        except MarketDataError as exc:
            return ProviderResult(ok=False, error=str(exc))
        except OSError as exc:
            return ProviderResult(ok=False, error=f"파일을 읽을 수 없습니다: {exc}")

        if start or end:
            lo = _parse_date(start) if start else 0
            hi = _parse_date(end) if end else 2 ** 62
            bars.bars = [b for b in bars.bars if lo <= b.ts <= hi]

        quality = check_quality(bars, exchange=self.exchange)
        return ProviderResult(ok=True, bars=bars, quality=quality)

    def health(self) -> dict:
        files = self.available()
        return {
            "id": self.id,
            "name": self.name,
            "requires_key": False,
            "cost": "무료",
            "directory": str(self.directory),
            "symbols_found": files,
            "status": "CONNECTED" if files else "EMPTY",
            "verified": self.verified,
            "terms_note": self.terms_note,
        }
