"""DART 응답 해석.

★ 이 파일에서 가장 중요한 한 가지 (SEC EDGAR 와 똑같습니다)

    공시에는 **두 개의 날짜**가 있습니다.

        결산기말 / 보고 대상 기간   그 숫자가 '언제의 실적인가'   (2024-12-31)
        rcept_dt (접수일자)         그 숫자가 '언제 공개됐는가'   (2025-03-14)

    `결산기말` 을 기준으로 쓰면 **12월 31일에 이미 연간 실적을 아는 것**이
    됩니다. 실제로는 3월 중순에야 알 수 있었습니다.
    **두 달 반의 미래를 보는 셈**입니다.

    그래서 PIT Store 에 넣을 때 `published_time` 은 반드시 `rcept_dt` 입니다.

★ 재무제표 API 의 함정

    `fnlttSinglAcnt.json` 은 숫자를 주지만 **언제 공시됐는지는 주지 않습니다.**
    그 숫자만 보고 저장하면 언제 알 수 있었는지 모르는 값이 됩니다.
    그래서 이 코드는 **접수일자 없이는 PIT 레코드를 만들지 않습니다.**
    반드시 목록 API(list.json)의 rcept_dt 와 짝지어야 합니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


class DartParseError(ValueError):
    """응답 형식이 예상과 다를 때."""


# DART 공통 상태 코드
STATUS = {
    "000": "정상",
    "010": "등록되지 않은 키입니다",
    "011": "사용할 수 없는 키입니다 (오픈API에 등록되었으나 일시적으로 사용 중지)",
    "012": "접근할 수 없는 IP 입니다",
    "013": "조회된 데이터가 없습니다",
    "014": "파일이 존재하지 않습니다",
    "020": "요청 제한을 초과했습니다 (일일 20,000건)",
    "021": "조회 가능한 회사 개수가 초과했습니다",
    "100": "필드의 부적절한 값입니다",
    "101": "부적절한 접근입니다",
    "800": "시스템 점검으로 서비스가 중지 중입니다",
    "900": "정의되지 않은 오류가 발생했습니다",
    "901": "사용자 계정의 이용가능 여부가 유효하지 않습니다",
}

# 사용자가 조치할 수 있는 것과 아닌 것을 구분해 안내합니다
_ACTIONABLE = {
    "010": "opendart.fss.or.kr 에서 인증키를 다시 확인하세요.",
    "011": "키가 일시 중지되었습니다. DART 사이트에서 상태를 확인하세요.",
    "013": "해당 조건에 공시가 없습니다. 기간이나 종목코드를 넓혀보세요.",
    "020": "오늘 한도(20,000건)를 다 썼습니다. 내일 다시 시도하세요.",
    "100": "요청 값이 잘못되었습니다 (종목코드 6자리·날짜 YYYYMMDD 확인).",
    "800": "DART 시스템 점검 중입니다. 잠시 후 다시 시도하세요.",
    "901": "계정 상태를 DART 사이트에서 확인하세요.",
}


def _to_ts(yyyymmdd: str | None) -> int | None:
    if not yyyymmdd:
        return None
    text = str(yyyymmdd).strip().replace("-", "")[:8]
    try:
        return int(datetime.strptime(text, "%Y%m%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def check_status(payload: dict) -> None:
    """DART 는 HTTP 200 으로 오류를 돌려줍니다. status 를 반드시 봐야 합니다."""
    status = str(payload.get("status", "")).strip()
    if status in ("", "000"):
        return
    why = STATUS.get(status, payload.get("message", "알 수 없는 오류"))
    hint = _ACTIONABLE.get(status, "")
    raise DartParseError(f"DART 오류 [{status}] {why}" + (f" — {hint}" if hint else ""))


@dataclass
class Filing:
    """공시 한 건."""
    rcept_no: str                 # 접수번호 (원문 링크의 열쇠)
    corp_name: str
    corp_code: str = ""
    stock_code: str = ""
    report_nm: str = ""           # 보고서명
    rcept_dt: str = ""            # ★ 접수일자 = 공개일 = PIT 기준
    flr_nm: str = ""              # 제출인
    corp_cls: str = ""            # Y(유가) K(코스닥) N(코넥스) E(기타)
    rm: str = ""                  # 비고

    @property
    def rcept_ts(self) -> int | None:
        return _to_ts(self.rcept_dt)

    @property
    def market(self) -> str:
        return {"Y": "KOSPI", "K": "KOSDAQ",
                "N": "KONEX", "E": "기타"}.get(self.corp_cls, self.corp_cls)

    def url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.rcept_no}"

    def to_dict(self) -> dict:
        return {
            "rcept_no": self.rcept_no,
            "corp_name": self.corp_name,
            "corp_code": self.corp_code,
            "stock_code": self.stock_code,
            "report_nm": self.report_nm,
            "rcept_dt": self.rcept_dt,
            "filer": self.flr_nm,
            "market": self.market,
            "remark": self.rm,
            "url": self.url(),
            "pit_note": ("published_time 은 rcept_dt(접수일자)입니다. "
                         "결산기말을 기준으로 쓰면 몇 달의 미래를 보게 됩니다."),
        }


def parse_filing_list(raw: bytes | str) -> tuple[dict, list[Filing]]:
    """`/api/list.json` 을 해석합니다."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise DartParseError(f"JSON 이 아닙니다: {exc}") from exc
    if not isinstance(data, dict):
        raise DartParseError("최상위가 객체가 아닙니다")

    check_status(data)

    meta = {
        "page_no": data.get("page_no"),
        "page_count": data.get("page_count"),
        "total_count": data.get("total_count"),
        "total_page": data.get("total_page"),
    }
    out: list[Filing] = []
    for row in data.get("list") or []:
        if not isinstance(row, dict) or not row.get("rcept_no"):
            continue
        out.append(Filing(
            rcept_no=str(row.get("rcept_no", "")),
            corp_name=str(row.get("corp_name", "")),
            corp_code=str(row.get("corp_code", "")),
            stock_code=str(row.get("stock_code", "") or ""),
            report_nm=str(row.get("report_nm", "")),
            rcept_dt=str(row.get("rcept_dt", "")),
            flr_nm=str(row.get("flr_nm", "")),
            corp_cls=str(row.get("corp_cls", "")),
            rm=str(row.get("rm", "") or ""),
        ))
    return meta, out


# ------------------------------------------------------------------ 재무제표
@dataclass
class FinancialItem:
    account_nm: str               # 계정명 (매출액, 영업이익 …)
    fs_div: str = ""              # CFS(연결) / OFS(별도)
    sj_div: str = ""              # BS(재무상태표) / IS(손익계산서)
    thstrm_nm: str = ""           # 당기명
    thstrm_amt: float | None = None
    frmtrm_amt: float | None = None
    bfefrmtrm_amt: float | None = None
    corp_code: str = ""
    bsns_year: str = ""
    reprt_code: str = ""
    # ★ 이 API 는 접수일자를 주지 않습니다. 밖에서 넣어줘야 합니다.
    rcept_no: str = ""

    def to_dict(self) -> dict:
        return {
            "account": self.account_nm,
            "fs_div": "연결" if self.fs_div == "CFS" else (
                "별도" if self.fs_div == "OFS" else self.fs_div),
            "statement": self.sj_div,
            "period": self.thstrm_nm,
            "amount": self.thstrm_amt,
            "prev_amount": self.frmtrm_amt,
            "prev2_amount": self.bfefrmtrm_amt,
            "fiscal_year": self.bsns_year,
            "report_code": self.reprt_code,
            "rcept_no": self.rcept_no,
        }


def _amount(text) -> float | None:
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_financials(raw: bytes | str) -> list[FinancialItem]:
    """`/api/fnlttSinglAcnt.json` (단일회사 주요계정) 을 해석합니다."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise DartParseError(f"JSON 이 아닙니다: {exc}") from exc

    check_status(data)

    out: list[FinancialItem] = []
    for row in data.get("list") or []:
        if not isinstance(row, dict) or not row.get("account_nm"):
            continue
        out.append(FinancialItem(
            account_nm=str(row.get("account_nm", "")),
            fs_div=str(row.get("fs_div", "")),
            sj_div=str(row.get("sj_div", "")),
            thstrm_nm=str(row.get("thstrm_nm", "")),
            thstrm_amt=_amount(row.get("thstrm_amt")),
            frmtrm_amt=_amount(row.get("frmtrm_amt")),
            bfefrmtrm_amt=_amount(row.get("bfefrmtrm_amt")),
            corp_code=str(row.get("corp_code", "")),
            bsns_year=str(row.get("bsns_year", "")),
            reprt_code=str(row.get("reprt_code", "")),
            rcept_no=str(row.get("rcept_no", "") or ""),
        ))
    return out


# ------------------------------------------------------------------ PIT
def filings_as_pit_records(filings: list[Filing]) -> list[dict]:
    """공시 목록을 PIT 레코드로. published_time = 접수일자."""
    records = []
    for f in filings:
        ts = f.rcept_ts
        if ts is None:
            continue          # 접수일자가 없으면 쓸 수 없습니다
        records.append({
            "key": f"{f.stock_code or f.corp_code}:filing:{f.rcept_no}",
            "value": f.report_nm,
            "event_time": ts,
            "published_time": ts,
            "source_id": f"dart:{f.corp_code}",
        })
    return records


def financials_as_pit_records(items: list[FinancialItem], stock_code: str,
                              rcept_dt: str) -> list[dict]:
    """재무 항목을 PIT 레코드로.

    ★ `rcept_dt` 가 없으면 **아무것도 만들지 않습니다.**
      언제 알 수 있었는지 모르는 숫자는 백테스트에 쓸 수 없습니다.
      결산기말을 대신 쓰는 순간 두 달 이상의 미래를 보게 됩니다.
    """
    pub = _to_ts(rcept_dt)
    if pub is None:
        raise DartParseError(
            "접수일자(rcept_dt) 없이는 PIT 레코드를 만들 수 없습니다. "
            "list.json 으로 해당 보고서의 접수일자를 먼저 확인하세요. "
            "결산기말을 공개일로 쓰면 몇 달의 미래를 보게 됩니다."
        )
    records = []
    for it in items:
        if it.thstrm_amt is None:
            continue
        records.append({
            "key": f"{stock_code}:{it.fs_div}:{it.account_nm}:{it.bsns_year}"
                   f":{it.reprt_code}",
            "value": it.thstrm_amt,
            "event_time": pub,
            "published_time": pub,
            "source_id": f"dart:{it.corp_code}",
            "period": it.thstrm_nm,
        })
    return records
