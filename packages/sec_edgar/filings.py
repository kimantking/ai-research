"""EDGAR 응답 해석.

★ 이 파일에서 가장 중요한 한 가지

    공시에는 **두 개의 날짜**가 있습니다.

        period_of_report  그 숫자가 '언제의 실적인가'   (예: 2024-09-28 분기말)
        filing_date       그 숫자가 '언제 공개됐는가'   (예: 2024-11-01)

    백테스트에서 `period_of_report` 를 기준으로 쓰면,
    **9월 28일에 이미 3분기 매출을 아는 것**이 됩니다.
    실제로는 11월 1일에야 알 수 있었습니다. 한 달의 미래를 보는 셈입니다.

    이것이 퀀트에서 가장 흔하고 가장 치명적인 look-ahead bias 입니다.
    그래서 이 코드는 두 날짜를 **절대 섞지 않고**, PIT Store 에 넣을 때
    `published_time` 은 반드시 `filing_date` 를 씁니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class ParseError(ValueError):
    """응답 형식이 예상과 다를 때."""


def _to_ts(text: str | None) -> int | None:
    if not text:
        return None
    try:
        d = datetime.strptime(text.strip()[:10], "%Y-%m-%d")
        return int(d.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


@dataclass
class Filing:
    accession: str
    form: str                       # 10-K, 10-Q, 8-K …
    filing_date: str                # ★ 공개된 날 — PIT 기준
    period_of_report: str = ""      # ★ 실적 기간 — PIT 기준이 아님
    primary_document: str = ""
    items: str = ""
    cik: str = ""

    @property
    def filing_ts(self) -> int | None:
        return _to_ts(self.filing_date)

    @property
    def period_ts(self) -> int | None:
        return _to_ts(self.period_of_report)

    @property
    def reporting_lag_days(self) -> int | None:
        """실적 기간 끝에서 공시까지 며칠 걸렸는가.

        이 값만큼이 곧 '이 데이터를 며칠 일찍 봤을 때 생기는 이득'입니다.
        보통 30~60일입니다. 결코 작지 않습니다.
        """
        f, p = self.filing_ts, self.period_ts
        if f is None or p is None:
            return None
        return (f - p) // 86_400

    def url(self) -> str:
        acc = self.accession.replace("-", "")
        cik = self.cik.lstrip("0") or "0"
        return (f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
                f"{self.primary_document}")

    def to_dict(self) -> dict:
        return {
            "accession": self.accession,
            "form": self.form,
            "filing_date": self.filing_date,
            "period_of_report": self.period_of_report,
            "reporting_lag_days": self.reporting_lag_days,
            "url": self.url() if self.primary_document else "",
            "pit_note": ("published_time 은 filing_date 입니다. "
                         "period_of_report 를 쓰면 미래를 보게 됩니다."),
        }


@dataclass
class CompanyFacts:
    cik: str
    name: str
    facts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"cik": self.cik, "name": self.name,
                "fact_count": len(self.facts), "facts": self.facts[:50]}


# ------------------------------------------------------------------ submissions
def parse_submissions(raw: bytes | str) -> tuple[dict, list[Filing]]:
    """`/submissions/CIK##########.json` 을 해석합니다.

    EDGAR 는 표를 '컬럼별 배열'로 줍니다. 행으로 되돌려야 합니다.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ParseError(f"JSON 이 아닙니다: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("최상위가 객체가 아닙니다")

    cik = str(data.get("cik", "")).zfill(10)
    meta = {
        "cik": cik,
        "name": data.get("name", ""),
        "tickers": data.get("tickers", []) or [],
        "exchanges": data.get("exchanges", []) or [],
        "sic_description": data.get("sicDescription", ""),
    }

    recent = ((data.get("filings") or {}).get("recent")) or {}
    if not recent:
        return meta, []

    forms = recent.get("form") or []
    accessions = recent.get("accessionNumber") or []
    filing_dates = recent.get("filingDate") or []
    periods = recent.get("reportDate") or []
    docs = recent.get("primaryDocument") or []
    items = recent.get("items") or []

    n = min(len(forms), len(accessions), len(filing_dates))
    if n == 0:
        return meta, []

    def at(seq, i, default=""):
        return seq[i] if i < len(seq) and seq[i] is not None else default

    out: list[Filing] = []
    for i in range(n):
        out.append(Filing(
            accession=str(accessions[i]),
            form=str(forms[i]),
            filing_date=str(filing_dates[i]),
            period_of_report=str(at(periods, i)),
            primary_document=str(at(docs, i)),
            items=str(at(items, i)),
            cik=cik,
        ))
    return meta, out


# ------------------------------------------------------------------ companyfacts
def parse_company_facts(raw: bytes | str, taxonomy: str = "us-gaap",
                        max_facts: int = 5000) -> CompanyFacts:
    """`/api/xbrl/companyfacts/CIK##########.json` 을 해석합니다.

    각 사실에 반드시 `filed`(공시일)를 붙입니다. 이것이 PIT 기준입니다.
    `end`(기간 끝)만 있고 `filed` 가 없는 항목은 **버립니다** —
    언제 알 수 있었는지 모르는 값은 쓸 수 없습니다.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ParseError(f"JSON 이 아닙니다: {exc}") from exc

    cik = str(data.get("cik", "")).zfill(10)
    name = data.get("entityName", "")
    facts_root = (data.get("facts") or {}).get(taxonomy) or {}

    out: list[dict] = []
    dropped_no_filed = 0
    for concept, body in facts_root.items():
        units = (body or {}).get("units") or {}
        label = (body or {}).get("label", concept)
        for unit, rows in units.items():
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                filed = row.get("filed")
                if not filed:
                    # ★ 언제 공개됐는지 모르는 값은 쓰지 않습니다.
                    dropped_no_filed += 1
                    continue
                out.append({
                    "concept": concept,
                    "label": label,
                    "unit": unit,
                    "value": row.get("val"),
                    "period_start": row.get("start", ""),
                    "period_end": row.get("end", ""),
                    "filed": filed,                    # ★ PIT 기준
                    "form": row.get("form", ""),
                    "fiscal_year": row.get("fy"),
                    "fiscal_period": row.get("fp", ""),
                    "frame": row.get("frame", ""),
                })
                if len(out) >= max_facts:
                    break

    out.sort(key=lambda f: (f["filed"], f["concept"]))
    cf = CompanyFacts(cik=cik, name=name, facts=out)
    if dropped_no_filed:
        cf.facts_dropped_no_filed = dropped_no_filed   # type: ignore[attr-defined]
    return cf


def facts_as_pit_records(cf: CompanyFacts, ticker: str) -> list[dict]:
    """PIT Store 에 넣을 형태로 바꿉니다.

    published_time = filed (공시일)   ← ★ 절대 period_end 가 아닙니다
    event_time     = period_end (그 실적이 속한 기간의 끝)
    """
    records = []
    for f in cf.facts:
        pub = _to_ts(f.get("filed"))
        evt = _to_ts(f.get("period_end")) or pub
        if pub is None:
            continue
        if evt is not None and evt > pub:
            # 기간 끝이 공시일보다 뒤인 이상한 행 — 공시일로 맞춥니다.
            evt = pub
        records.append({
            "key": f"{ticker.upper()}:{f['concept']}:{f.get('period_end','')}",
            "value": f.get("value"),
            "event_time": evt,
            "published_time": pub,
            "source_id": f"sec_edgar:{cf.cik}",
            "unit": f.get("unit"),
            "form": f.get("form"),
        })
    return records
