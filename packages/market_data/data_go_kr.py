"""공공데이터포털 — 금융위원회 주식시세정보 (한국 일별 시세).

★ 왜 이것을 고르는가 (한국 주식 기준)

    - **한국 정부 공식 데이터**입니다. 비공식 스크래핑이 아닙니다.
    - **무료**이고, 개발계정은 보통 자동 승인됩니다.
    - 약관이 명확하고 관대합니다 (공공데이터법).
    - KOSPI / KOSDAQ / KONEX 를 모두 포함합니다.

★ 엔드포인트

    GET https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo
        ?serviceKey=...&resultType=json&numOfRows=1000&pageNo=1
        &likeSrtnCd=005930&beginBasDt=20240101&endBasDt=20241231

★ 이 파일에서 가장 신경 쓴 두 가지

    1. **serviceKey 인코딩 지옥**
       data.go.kr 은 키를 'Encoding' / 'Decoding' 두 형태로 줍니다.
       Decoding 키에는 `+` `/` `=` 가 들어 있어 그대로 URL 에 붙이면 깨집니다.
       (`+` 가 공백으로 해석됩니다 — 이게 이 API 최대의 함정입니다)
       그래서 어느 쪽을 주셔도 되도록 **자동 판별**합니다.

    2. **JSON 을 요청했는데 XML 오류가 돌아옵니다**
       키가 틀리거나 미승인이면 `resultType=json` 을 무시하고
       `<OpenAPI_ServiceResponse>` XML 을 줍니다. 이걸 처리하지 않으면
       "JSON 파싱 실패" 라는 쓸모없는 오류만 남습니다.
       실제 사유(미등록 키·한도초과·미승인)를 뽑아서 알려줍니다.

★ 검증 상태

    파싱·정규화·페이징·오류처리·품질검사  ✅ 실제 응답 형식으로 테스트 완료
    실제 서버 연결                        ❌ 미검증 (이 개발 환경은 외부망 차단)

    코드는 공개 명세 기준으로 작성했습니다. 실제 동작은 antking님 PC 에서
    처음 확인됩니다. 실패하면 사유를 명확히 말하도록 만들어 두었습니다.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import quote

from .base import (
    Bar,
    Bars,
    MarketDataError,
    ProviderResult,
    Transport,
    UrlTransport,
    check_quality,
)

BASE = ("https://apis.data.go.kr/1160100/service/"
        "GetStockSecuritiesInfoService/getStockPriceInfo")

# 응답 헤더의 resultCode → 사람이 읽을 수 있는 설명
_RESULT_CODES = {
    "00": "정상",
    "01": "어플리케이션 에러",
    "02": "데이터베이스 에러",
    "03": "데이터 없음",
    "04": "HTTP 에러",
    "05": "서비스 연결 실패",
    "10": "잘못된 요청 파라미터",
    "11": "필수 요청 파라미터 누락",
    "12": "해당 오픈 API 서비스가 없거나 폐기됨",
    "20": "서비스 접근 거부",
    "21": "일시적으로 사용할 수 없는 서비스 키",
    "22": "서비스 요청 제한 횟수 초과",
    "30": "등록되지 않은 서비스 키",
    "31": "기한 만료된 서비스 키",
    "32": "등록되지 않은 IP",
    "99": "기타 에러",
}

# XML 오류 응답에 들어오는 문자열 → 우리말 안내
_XML_HINTS = {
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR": (
        "등록되지 않은 서비스 키입니다. "
        "data.go.kr 마이페이지에서 '금융위원회_주식시세정보' 활용신청이 "
        "승인되었는지, 키를 정확히 복사했는지 확인하세요."
    ),
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": (
        "일일 호출 한도를 초과했습니다. 내일 다시 시도하거나 "
        "data.go.kr 에서 한도 증가를 신청하세요."
    ),
    "SERVICE_ACCESS_DENIED_ERROR": (
        "이 서비스에 대한 접근이 거부되었습니다. 활용신청 승인 상태를 확인하세요."
    ),
    "UNREGISTERED_IP_ERROR": "등록되지 않은 IP 입니다.",
    "DEADLINE_HAS_EXPIRED_ERROR": "서비스 키 사용 기한이 만료되었습니다.",
    "NO_OPENAPI_SERVICE_ERROR": "해당 오픈 API 서비스가 없거나 폐기되었습니다.",
}


def _looks_url_encoded(key: str) -> bool:
    """이미 URL 인코딩된 키인지(=Encoding 키인지) 추정합니다.

    Decoding 키에는 보통 `+` `/` `=` 가 그대로 들어 있고,
    Encoding 키에는 그것들이 `%2B` `%2F` `%3D` 로 바뀌어 있습니다.
    """
    k = key.strip()
    if any(tok in k for tok in ("%2B", "%2F", "%3D", "%2b", "%2f", "%3d")):
        return True
    # 원문 특수문자가 하나도 없고 %가 있으면 인코딩된 것으로 봅니다
    return "%" in k and not any(c in k for c in "+/=")


def _parse_basdt(text: str) -> int:
    """'20240102' → epoch(UTC 자정)."""
    d = datetime.strptime(text.strip(), "%Y%m%d").replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def _num(value, field: str, row: dict) -> float:
    if value is None or str(value).strip() in ("", "-"):
        raise MarketDataError(f"{field} 값이 비어 있습니다: {row.get('basDt')}")
    return float(str(value).replace(",", ""))


class DataGoKrProvider:
    """금융위원회 주식시세정보 (공공데이터포털)."""

    id = "data_go_kr"
    name = "공공데이터포털 (금융위 주식시세)"
    requires_key = True
    key_env = "DATA_GO_KR_KEY"
    terms_note = (
        "한국 정부 공개 데이터입니다(공공데이터법). 무료이며 이용·재배포 조건이 "
        "명확합니다. 개발계정은 일일 호출 한도가 있으니 종목 수를 조절하세요."
    )
    verified = "파싱·페이징·오류처리 검증 완료 / 실제 서버 연결 미검증"

    def __init__(self, service_key: str = "", transport: Transport | None = None,
                 exchange: str = "XKRX", min_interval: float = 0.35,
                 max_pages: int = 20, rows_per_page: int = 1000):
        self.service_key = (service_key or "").strip()
        self.transport = transport or UrlTransport("airo-research/1.0")
        self.exchange = exchange
        self.min_interval = min_interval      # 예의 있는 호출 간격
        self.max_pages = max_pages
        self.rows_per_page = rows_per_page
        self._last_call = 0.0

    # ------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return len(self.service_key) >= 20

    def _encoded_key(self) -> str:
        """어느 형태를 주셔도 URL 에 안전하게 들어가도록 맞춥니다."""
        if not self.configured:
            raise MarketDataError(
                "공공데이터포털 서비스 키가 없습니다. "
                ".env 에 DATA_GO_KR_KEY=... 를 넣어주세요. "
                "(data.go.kr → 금융위원회_주식시세정보 → 활용신청 → 인증키)"
            )
        if _looks_url_encoded(self.service_key):
            return self.service_key            # 이미 인코딩됨 — 그대로
        # ★ Decoding 키는 반드시 인코딩해야 합니다.
        #   `+` 를 그대로 두면 서버가 공백으로 읽어 키가 틀렸다고 나옵니다.
        return quote(self.service_key, safe="")

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    # ------------------------------------------------------------------
    def url_for(self, symbol: str, start: str | None, end: str | None,
                page: int = 1) -> str:
        code = "".join(ch for ch in symbol if ch.isalnum())
        params = [
            f"serviceKey={self._encoded_key()}",
            "resultType=json",
            f"numOfRows={self.rows_per_page}",
            f"pageNo={page}",
            f"likeSrtnCd={quote(code, safe='')}",
        ]
        if start:
            params.append("beginBasDt=" + start.replace("-", ""))
        if end:
            params.append("endBasDt=" + end.replace("-", ""))
        return BASE + "?" + "&".join(params)

    # ------------------------------------------------------------------
    @staticmethod
    def _explain_xml_error(text: str) -> str:
        """JSON 을 요청했는데 XML 오류가 온 경우 — 진짜 사유를 뽑아냅니다."""
        for token, message in _XML_HINTS.items():
            if token in text:
                return message
        # 그래도 모르면 원문 일부를 보여줍니다 (침묵보다 낫습니다)
        snippet = " ".join(text.split())[:200]
        return f"서버가 오류 XML 을 돌려주었습니다: {snippet}"

    def parse_page(self, raw: bytes, symbol: str) -> tuple[list[Bar], int]:
        """한 페이지를 해석해 (봉 목록, 전체 건수) 를 돌려줍니다."""
        text = raw.decode("utf-8", errors="replace").strip()

        if text.startswith("<"):
            raise MarketDataError(self._explain_xml_error(text))

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MarketDataError(
                f"응답을 JSON 으로 읽지 못했습니다: {exc}. "
                f"앞부분: {text[:120]}"
            ) from exc

        response = data.get("response") or {}
        header = response.get("header") or {}
        code = str(header.get("resultCode", "")).zfill(2)
        if code and code != "00":
            why = _RESULT_CODES.get(code, header.get("resultMsg", "알 수 없는 오류"))
            if code == "03":
                raise MarketDataError(
                    f"{symbol}: 해당 기간에 데이터가 없습니다 "
                    f"(종목코드·기간을 확인하세요)")
            raise MarketDataError(f"공공데이터포털 오류 [{code}] {why}")

        body = response.get("body") or {}
        total = int(body.get("totalCount") or 0)
        items = body.get("items") or {}
        rows = items.get("item") if isinstance(items, dict) else items
        if rows is None:
            return [], total
        if isinstance(rows, dict):        # 1건이면 리스트가 아니라 객체로 옵니다
            rows = [rows]

        bars: list[Bar] = []
        skipped = 0
        for row in rows:
            if not isinstance(row, dict):
                skipped += 1
                continue
            try:
                bars.append(Bar(
                    ts=_parse_basdt(str(row["basDt"])),
                    open=_num(row.get("mkp"), "시가", row),
                    high=_num(row.get("hipr"), "고가", row),
                    low=_num(row.get("lopr"), "저가", row),
                    close=_num(row.get("clpr"), "종가", row),
                    volume=float(str(row.get("trqu") or 0).replace(",", "")),
                ))
            except (KeyError, ValueError, MarketDataError):
                skipped += 1
                continue
        return bars, total

    # ------------------------------------------------------------------
    def fetch(self, symbol: str, start: str | None = None,
              end: str | None = None) -> ProviderResult:
        try:
            all_bars: list[Bar] = []
            page = 1
            total = 0
            while page <= self.max_pages:
                self._throttle()
                raw = self.transport.get(self.url_for(symbol, start, end, page))
                bars, total = self.parse_page(raw, symbol)
                all_bars.extend(bars)
                if not bars or len(all_bars) >= total or total == 0:
                    break
                page += 1

            if not all_bars:
                return ProviderResult(
                    ok=False,
                    error=(f"{symbol}: 받은 데이터가 없습니다. "
                           f"종목코드 6자리(예: 005930)와 기간을 확인하세요."))

            # 같은 날짜가 페이지 경계에서 겹칠 수 있으므로 정리합니다
            seen: dict[int, Bar] = {}
            for b in all_bars:
                seen[b.ts] = b
            ordered = [seen[k] for k in sorted(seen)]

            out = Bars(symbol=symbol.upper(), bars=ordered, source=self.id,
                       adjusted=False, currency="KRW")
            out.notes.append(
                "금융위원회 주식시세정보는 **수정주가가 아닌 원주가**입니다. "
                "액면분할·병합 구간은 품질 보고서의 extreme_moves 를 확인하세요."
            )
            if page > 1:
                out.notes.append(f"{page}개 페이지를 이어붙였습니다 (전체 {total}건)")
        except MarketDataError as exc:
            return ProviderResult(ok=False, error=str(exc))
        except Exception as exc:                          # pragma: no cover
            return ProviderResult(ok=False, error=f"예상치 못한 오류: {exc}")

        quality = check_quality(out, exchange=self.exchange)
        return ProviderResult(ok=True, bars=out, quality=quality)

    # ------------------------------------------------------------------
    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": "READY" if self.configured else "NEEDS_KEY",
            "requires_key": True,
            "key_env": self.key_env,
            "cost": "무료",
            "verified": self.verified,
            "terms_note": self.terms_note,
            "detail": ("준비됨" if self.configured else
                       ".env 에 DATA_GO_KR_KEY 를 설정하세요 "
                       "(data.go.kr 가입 → 금융위원회_주식시세정보 활용신청, 무료)"),
        }
