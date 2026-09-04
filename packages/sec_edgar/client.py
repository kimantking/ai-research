"""SEC EDGAR 클라이언트 (표준 라이브러리만).

★ SEC 가 요구하는 것 (sec.gov/os/accessing-edgar-data 에 명시)

    1. **User-Agent 에 연락 가능한 이메일**을 넣어야 합니다.
       넣지 않으면 차단됩니다. 이것은 예의가 아니라 규칙입니다.
    2. **초당 10요청**을 넘으면 안 됩니다.
    3. 데이터 자체는 공개 자료이며 자유롭게 이용·재배포할 수 있습니다.

    이 세 가지를 코드가 강제합니다. 특히 (1) 은 **이메일이 없으면
    아예 요청을 만들지 않습니다.** "일단 보내보고 막히면 알려주기"는
    상대 서버에 폐를 끼치는 방식입니다.

★ 검증 상태
    Rate limiter, User-Agent 강제, 파싱: ✅ 테스트 완료
    실제 SEC 서버 연결:                  ❌ 미검증 (이 환경은 외부 접속 차단)
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from .filings import CompanyFacts, Filing, ParseError, parse_company_facts, parse_submissions

BASE_DATA = "https://data.sec.gov"
BASE_WWW = "https://www.sec.gov"

MAX_BYTES = 40 * 1024 * 1024      # companyfacts 는 큽니다


class EdgarError(RuntimeError):
    """EDGAR 를 쓸 수 없거나 규칙을 지킬 수 없을 때."""


# ------------------------------------------------------------------ 속도 제한
class RateLimiter:
    """초당 N회를 **넘지 못하게** 막습니다 (슬라이딩 윈도우).

    '평균 10회'가 아니라 '어느 1초 구간에서도 10회 이하'입니다.
    평균만 맞추면 순간적으로 몰려서 차단당합니다.
    """

    def __init__(self, per_second: int = 10, sleeper=time.sleep,
                 clock=time.monotonic):
        if per_second < 1:
            raise ValueError("per_second 는 1 이상이어야 합니다")
        self.per_second = per_second
        self._calls: deque[float] = deque()
        self._sleep = sleeper
        self._clock = clock

    def acquire(self) -> float:
        """호출 직전에 부릅니다. 기다린 시간(초)을 돌려줍니다."""
        waited = 0.0
        while True:
            now = self._clock()
            while self._calls and now - self._calls[0] >= 1.0:
                self._calls.popleft()
            if len(self._calls) < self.per_second:
                self._calls.append(now)
                return waited
            sleep_for = 1.0 - (now - self._calls[0]) + 0.001
            self._sleep(max(sleep_for, 0.001))
            waited += max(sleep_for, 0.001)


# ------------------------------------------------------------------ 클라이언트
@dataclass
class EdgarStats:
    requests: int = 0
    bytes_received: int = 0
    throttled_seconds: float = 0.0
    errors: int = 0


class EdgarClient:
    id = "sec_edgar"
    name = "SEC EDGAR"
    requires_key = False
    terms_note = (
        "SEC EDGAR 자료는 공개 자료로 자유롭게 이용·재배포할 수 있습니다. "
        "다만 User-Agent 에 연락 가능한 이메일이 필수이고, "
        "초당 10요청을 넘으면 차단됩니다."
    )
    verified = "속도제한·UA 강제·파서 검증 완료 / 실제 서버 연결 미검증"

    def __init__(self, contact_email: str = "", app_name: str = "airo-research",
                 transport=None, per_second: int = 10):
        self.contact_email = (contact_email or "").strip()
        self.app_name = app_name
        self.transport = transport
        self.limiter = RateLimiter(per_second)
        self.stats = EdgarStats()

    # ------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return "@" in self.contact_email and "." in self.contact_email.split("@")[-1]

    def user_agent(self) -> str:
        if not self.configured:
            raise EdgarError(
                "SEC 는 User-Agent 에 연락 가능한 이메일을 요구합니다. "
                ".env 의 SEC_CONTACT_EMAIL 을 채워주세요. "
                "(예: SEC_CONTACT_EMAIL=you@example.com) "
                "— 이메일 없이 요청을 보내면 차단되며, 그것은 상대 서버에 "
                "폐를 끼치는 일이라 아예 시도하지 않습니다."
            )
        return f"{self.app_name} {self.contact_email}"

    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": "READY" if self.configured else "NEEDS_CONTACT_EMAIL",
            "requires_key": False,
            "cost": "무료",
            "rate_limit": f"{self.limiter.per_second} req/sec",
            "contact_email_set": self.configured,
            "verified": self.verified,
            "terms_note": self.terms_note,
            "detail": ("준비됨" if self.configured else
                       ".env 에 SEC_CONTACT_EMAIL 을 설정하세요 (비용 없음)"),
            "stats": {
                "requests": self.stats.requests,
                "bytes": self.stats.bytes_received,
                "throttled_seconds": round(self.stats.throttled_seconds, 3),
                "errors": self.stats.errors,
            },
        }

    # ------------------------------------------------------------------
    def _get(self, url: str) -> bytes:
        ua = self.user_agent()                 # 이메일 없으면 여기서 멈춥니다
        self.stats.throttled_seconds += self.limiter.acquire()

        transport = self.transport
        if transport is None:
            from packages.market_data.base import UrlTransport
            transport = UrlTransport(user_agent=ua)
            self.transport = transport

        headers = {"User-Agent": ua, "Accept": "application/json"}
        try:
            raw = transport.get(url, headers=headers, timeout=30.0)
        except Exception as exc:
            self.stats.errors += 1
            raise EdgarError(str(exc)) from exc

        self.stats.requests += 1
        self.stats.bytes_received += len(raw)
        if len(raw) > MAX_BYTES:
            raise EdgarError(f"응답이 너무 큽니다 ({len(raw)} bytes)")
        return raw

    # ------------------------------------------------------------------
    @staticmethod
    def normalize_cik(cik: str | int) -> str:
        digits = "".join(ch for ch in str(cik) if ch.isdigit())
        if not digits:
            raise EdgarError(f"CIK 가 아닙니다: {cik!r}")
        return digits.zfill(10)

    def submissions_url(self, cik: str | int) -> str:
        return f"{BASE_DATA}/submissions/CIK{self.normalize_cik(cik)}.json"

    def company_facts_url(self, cik: str | int) -> str:
        return (f"{BASE_DATA}/api/xbrl/companyfacts/"
                f"CIK{self.normalize_cik(cik)}.json")

    # ------------------------------------------------------------------
    def fetch_filings(self, cik: str | int, forms: tuple[str, ...] = (),
                      limit: int = 40) -> dict:
        """최근 공시 목록. 실패해도 예외 대신 결과 딕셔너리를 돌려줍니다."""
        try:
            raw = self._get(self.submissions_url(cik))
            meta, filings = parse_submissions(raw)
        except (EdgarError, ParseError) as exc:
            return {"ok": False, "error": str(exc), "filings": []}

        if forms:
            wanted = {f.upper() for f in forms}
            filings = [f for f in filings if f.form.upper() in wanted]
        filings = filings[:limit]

        return {
            "ok": True,
            "company": meta,
            "filings": [f.to_dict() for f in filings],
            "count": len(filings),
            "pit_note": (
                "filing_date 가 '알 수 있었던 시각' 입니다. "
                "period_of_report 를 기준으로 쓰면 평균 30~60일의 미래를 봅니다."
            ),
        }

    def fetch_company_facts(self, cik: str | int, ticker: str = "") -> dict:
        try:
            raw = self._get(self.company_facts_url(cik))
            cf = parse_company_facts(raw)
        except (EdgarError, ParseError) as exc:
            return {"ok": False, "error": str(exc), "facts": []}

        return {
            "ok": True,
            "company": {"cik": cf.cik, "name": cf.name},
            "fact_count": len(cf.facts),
            "facts": cf.facts[:100],
            "dropped_without_filed_date": getattr(cf, "facts_dropped_no_filed", 0),
            "pit_note": (
                "'filed' 가 없는 항목은 언제 알 수 있었는지 알 수 없어 버립니다."
            ),
        }
