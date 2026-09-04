"""DART (금융감독원 전자공시) 클라이언트 — 표준 라이브러리만.

★ SEC EDGAR 와 같은 원칙을 씁니다

    1. 키가 없으면 **요청 자체를 만들지 않습니다.**
       "일단 보내보고 막히면 알려주기" 는 상대 서버에 폐를 끼칩니다.
    2. `rcept_dt`(접수일자) 와 결산기말을 **절대 섞지 않습니다.**
    3. 호출 간격을 둡니다 (일일 20,000건 한도).

★ 종목코드 → corp_code 변환

    DART 는 자체 8자리 `corp_code` 를 씁니다. 우리가 아는 건 6자리 종목코드
    (005930) 이므로 변환표가 필요합니다.
    `corpCode.xml` 은 **ZIP 파일**로 오며, 압축을 풀면 XML 하나가 나옵니다.
    한 번 받아서 저장소에 캐시해 두면 다시 받을 필요가 없습니다.

★ 검증 상태

    파싱·상태코드 처리·ZIP 해제·PIT 규칙  ✅ 실제 응답 형식으로 테스트 완료
    실제 DART 서버 연결                  ❌ 미검증 (이 개발 환경은 외부망 차단)
"""

from __future__ import annotations

import io
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

from .filings import (
    DartParseError,
    Filing,
    FinancialItem,
    filings_as_pit_records,
    parse_filing_list,
    parse_financials,
)

BASE = "https://opendart.fss.or.kr/api"
MAX_BYTES = 40 * 1024 * 1024      # corpCode.zip 이 큽니다

# 보고서 코드
REPORT_CODES = {
    "사업보고서": "11011",
    "반기보고서": "11012",
    "1분기보고서": "11013",
    "3분기보고서": "11014",
}


class DartError(RuntimeError):
    """DART 를 쓸 수 없거나 규칙을 지킬 수 없을 때."""


@dataclass
class DartStats:
    requests: int = 0
    bytes_received: int = 0
    errors: int = 0


class DartClient:
    id = "dart"
    name = "DART (금융감독원 전자공시)"
    requires_key = True
    key_env = "DART_API_KEY"
    terms_note = (
        "금융감독원 오픈API. 무료이며 일일 20,000건까지 호출할 수 있습니다. "
        "인증키는 opendart.fss.or.kr 에서 이메일 인증으로 즉시 발급됩니다."
    )
    verified = "파싱·상태코드·ZIP 해제·PIT 규칙 검증 완료 / 실제 서버 연결 미검증"

    def __init__(self, api_key: str = "", transport=None,
                 min_interval: float = 0.2):
        self.api_key = (api_key or "").strip()
        self.transport = transport
        self.min_interval = min_interval
        self.stats = DartStats()
        self._corp_map: dict[str, dict] = {}
        self._last_call = 0.0

    # ------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        # DART 인증키는 40자리 16진 문자열입니다.
        return bool(re.fullmatch(r"[0-9a-fA-F]{40}", self.api_key))

    def _require_key(self) -> str:
        if not self.api_key:
            raise DartError(
                "DART 인증키가 없습니다. .env 에 DART_API_KEY=... 를 넣어주세요. "
                "(opendart.fss.or.kr → 인증키 신청, 무료·즉시)"
            )
        if not self.configured:
            raise DartError(
                f"DART 인증키 형식이 아닙니다 (40자리 16진수여야 합니다, "
                f"입력된 길이: {len(self.api_key)}). 키를 다시 복사해 주세요."
            )
        return self.api_key

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict) -> bytes:
        key = self._require_key()          # 키 없으면 여기서 멈춥니다
        self._throttle()

        transport = self.transport
        if transport is None:
            from packages.market_data.base import UrlTransport
            transport = UrlTransport("airo-research/1.0")
            self.transport = transport

        from urllib.parse import quote
        query = "&".join(
            [f"crtfc_key={quote(key, safe='')}"]
            + [f"{k}={quote(str(v), safe='')}" for k, v in params.items()
               if v not in (None, "")]
        )
        url = f"{BASE}/{path}?{query}"
        try:
            raw = transport.get(url, timeout=30.0)
        except Exception as exc:
            self.stats.errors += 1
            raise DartError(str(exc)) from exc

        self.stats.requests += 1
        self.stats.bytes_received += len(raw)
        if len(raw) > MAX_BYTES:
            raise DartError(f"응답이 너무 큽니다 ({len(raw)} bytes)")
        return raw

    # ------------------------------------------------------------------ 공시 목록
    def fetch_filings(self, stock_code: str = "", corp_code: str = "",
                      begin: str = "", end: str = "",
                      report_types: str = "", limit: int = 50) -> dict:
        """최근 공시 목록. 실패해도 예외 대신 결과 딕셔너리를 돌려줍니다.

        stock_code 를 주면 corp_code 로 자동 변환합니다(변환표 필요).
        """
        try:
            if not corp_code and stock_code:
                corp_code = self.corp_code_for(stock_code)
            params = {
                "corp_code": corp_code,
                "bgn_de": begin.replace("-", "") if begin else "",
                "end_de": end.replace("-", "") if end else "",
                "pblntf_ty": report_types,
                "page_count": max(1, min(limit, 100)),
                "page_no": 1,
            }
            raw = self._get("list.json", params)
            meta, filings = parse_filing_list(raw)
        except (DartError, DartParseError) as exc:
            return {"ok": False, "error": str(exc), "filings": []}

        return {
            "ok": True,
            "meta": meta,
            "count": len(filings),
            "filings": [f.to_dict() for f in filings[:limit]],
            "pit_note": (
                "rcept_dt(접수일자)가 '알 수 있었던 시각' 입니다. "
                "결산기말을 기준으로 쓰면 사업보고서는 두 달 이상의 미래를 봅니다."
            ),
        }

    # ------------------------------------------------------------------ 재무제표
    def fetch_financials(self, stock_code: str, year: str,
                         report: str = "사업보고서",
                         rcept_dt: str = "") -> dict:
        """단일회사 주요계정.

        ★ `rcept_dt` 를 주지 않으면 PIT 레코드를 만들지 않습니다.
          이 API 는 접수일자를 돌려주지 않기 때문입니다.
          숫자는 보여드리되, "언제 알 수 있었는지 모른다" 고 명시합니다.
        """
        code = REPORT_CODES.get(report, report)
        try:
            corp_code = self.corp_code_for(stock_code)
            raw = self._get("fnlttSinglAcnt.json", {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": code,
            })
            items = parse_financials(raw)
        except (DartError, DartParseError) as exc:
            return {"ok": False, "error": str(exc), "items": []}

        result = {
            "ok": True,
            "stock_code": stock_code,
            "fiscal_year": str(year),
            "report": report,
            "count": len(items),
            "items": [i.to_dict() for i in items],
        }
        if rcept_dt:
            from .filings import financials_as_pit_records
            try:
                result["pit_records"] = len(
                    financials_as_pit_records(items, stock_code, rcept_dt))
                result["published_date"] = rcept_dt
            except DartParseError as exc:
                result["pit_warning"] = str(exc)
        else:
            result["pit_warning"] = (
                "★ 접수일자를 주지 않아 PIT 레코드를 만들지 않았습니다. "
                "이 숫자들이 언제 공개됐는지 알 수 없으므로 백테스트에 쓰면 "
                "미래 정보가 섞입니다. 먼저 공시 목록에서 해당 보고서의 "
                "rcept_dt 를 확인한 뒤 rcept_dt= 로 넘겨주세요."
            )
        return result

    # ------------------------------------------------------------------ 회사코드
    def load_corp_codes(self, raw: bytes | None = None) -> int:
        """종목코드 → corp_code 변환표를 만듭니다.

        `corpCode.xml` 은 ZIP 으로 옵니다. 안에 XML 하나가 들어 있습니다.
        """
        if raw is None:
            raw = self._get("corpCode.xml", {})

        # ZIP 이 아니면 대개 오류 JSON 입니다
        if not raw[:2] == b"PK":
            text = raw.decode("utf-8", errors="replace")[:300]
            if '"status"' in text:
                import json as _json
                from .filings import check_status
                try:
                    check_status(_json.loads(
                        raw.decode("utf-8", errors="replace")))
                except DartParseError as exc:
                    raise DartError(str(exc)) from exc
            raise DartError(f"ZIP 파일이 아닙니다. 응답 앞부분: {text[:150]}")

        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                if not names:
                    raise DartError("ZIP 안에 XML 이 없습니다")
                xml_bytes = zf.read(names[0])
        except zipfile.BadZipFile as exc:
            raise DartError(f"ZIP 을 열 수 없습니다: {exc}") from exc

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise DartError(f"XML 을 해석할 수 없습니다: {exc}") from exc

        mapping: dict[str, dict] = {}
        for item in root.iter("list"):
            stock = (item.findtext("stock_code") or "").strip()
            corp = (item.findtext("corp_code") or "").strip()
            name = (item.findtext("corp_name") or "").strip()
            if not corp:
                continue
            entry = {"corp_code": corp, "corp_name": name, "stock_code": stock}
            if stock:                       # 상장사만 종목코드로 찾을 수 있습니다
                mapping[stock] = entry
            mapping.setdefault("name:" + name, entry)
        self._corp_map = mapping
        return sum(1 for k in mapping if not k.startswith("name:"))

    def corp_code_for(self, stock_code: str) -> str:
        code = "".join(ch for ch in str(stock_code) if ch.isalnum()).zfill(6)
        if not self._corp_map:
            self.load_corp_codes()
        entry = self._corp_map.get(code)
        if entry is None:
            raise DartError(
                f"종목코드 {code} 에 해당하는 DART 회사를 찾지 못했습니다. "
                f"상장사 6자리 코드인지 확인하세요 (예: 삼성전자 005930)."
            )
        return entry["corp_code"]

    def corp_name_for(self, stock_code: str) -> str:
        code = "".join(ch for ch in str(stock_code) if ch.isalnum()).zfill(6)
        if not self._corp_map:
            self.load_corp_codes()
        entry = self._corp_map.get(code)
        return entry["corp_name"] if entry else ""

    # ------------------------------------------------------------------
    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": "READY" if self.configured else (
                "NEEDS_KEY" if not self.api_key else "BAD_KEY_FORMAT"),
            "requires_key": True,
            "key_env": self.key_env,
            "cost": "무료",
            "rate_limit": "20,000 req/day",
            "corp_codes_loaded": len(
                [k for k in self._corp_map if not k.startswith("name:")]),
            "verified": self.verified,
            "terms_note": self.terms_note,
            "detail": (
                "준비됨" if self.configured else
                (".env 에 DART_API_KEY 를 설정하세요 "
                 "(opendart.fss.or.kr → 인증키 신청, 무료)"
                 if not self.api_key else
                 "키 형식이 40자리 16진수가 아닙니다. 다시 복사해 주세요.")
            ),
            "stats": {
                "requests": self.stats.requests,
                "bytes": self.stats.bytes_received,
                "errors": self.stats.errors,
            },
        }
