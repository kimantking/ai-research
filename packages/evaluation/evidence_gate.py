"""Evidence Gate — 근거 없는 숫자가 있으면 리포트 발행을 '차단'합니다.

프로젝트 원칙 §25
    중요 숫자는 Evidence ID 없이 Final Report 에 포함하지 않는다.

★ 왜 예외를 던지는가
   경고 로그로 처리하면 아무도 안 봅니다.
   리포트가 아예 안 나가야 사람이 고칩니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 근거 표시 형식:  [E:evidence_id]
EVIDENCE_TAG = re.compile(r"\[E:([A-Za-z0-9_\-]+)\]")

# 리포트 본문에서 '주장에 해당하는 숫자'를 찾는 패턴.
#
# 단위가 붙은 수치(47%, $4.2 billion, 3조원)뿐 아니라
# 단위 없는 수치(지지선 182.45, RSI 71.3)도 잡습니다.
# 실제 리포트에서 위험한 숫자는 대부분 단위가 없기 때문입니다.
_UNIT = r"(?:%|퍼센트|억원|조원|억|조|만주|billion|million|bn|B|M|배|원|달러|USD)"
NUMBER_PATTERN = re.compile(
    r"(?:(?:\$|₩)\s?\d[\d,]*(?:\.\d+)?"          # 통화 기호가 앞에
    rf"|\d[\d,]*(?:\.\d+)?\s*{_UNIT}"             # 단위가 뒤에
    r"|\d[\d,]*\.\d+"                             # 소수 (예: 182.45)
    r"|\b\d{3,}(?:,\d{3})*\b)"                    # 세 자리 이상 정수
)

# 숫자로 세지 않는 것들 (오탐 방지)
_IGNORE_CONTEXT = re.compile(
    r"\[E:[^\]]*\]"          # 근거 태그 자체
    r"|\bEV\d+\b"            # 근거 ID
    r"|\d{4}-\d{2}-\d{2}"    # 날짜
    r"|\bp\d{4,}\b"          # 예측 ID
    r"|\bjob\d+\b"
)


class EvidenceMissing(Exception):
    def __init__(self, offenders: list[str], text: str):
        self.offenders = offenders
        self.text = text
        super().__init__(
            "근거 ID 없는 수치가 있어 리포트를 발행할 수 없습니다: "
            + ", ".join(offenders[:5])
        )


@dataclass
class GateReport:
    passed: bool
    checked_numbers: int = 0
    cited_numbers: int = 0
    offenders: list[str] = field(default_factory=list)
    unknown_evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checked_numbers": self.checked_numbers,
            "cited_numbers": self.cited_numbers,
            "offenders": self.offenders,
            "unknown_evidence_ids": self.unknown_evidence_ids,
        }


class EvidenceGate:
    """리포트 문장을 검사합니다.

    규칙: 숫자가 나오면 같은 문장 안에 [E:xxx] 태그가 있어야 합니다.
    """

    def __init__(self, known_evidence_ids: set[str] | None = None, strict: bool = True):
        self.known = known_evidence_ids or set()
        self.strict = strict

    @staticmethod
    def _split_units(text: str) -> list[str]:
        """검사 단위로 나눕니다.

        문장 끝의 마침표 때문에 "매출이 47% 늘었다. [E:EV001]" 이
        두 조각으로 갈리는 문제가 있어서, 근거 태그만 남은 조각은
        앞 문장에 다시 붙입니다. (근거는 보통 문장 뒤에 옵니다)
        """
        raw = re.split(r"(?<=[.!?。])\s+|\n+", text)
        units: list[str] = []
        for chunk in raw:
            if not chunk.strip():
                continue
            tags_only = EVIDENCE_TAG.sub("", chunk).strip() == ""
            if tags_only and units:
                units[-1] = units[-1] + " " + chunk.strip()
            else:
                units.append(chunk.strip())
        return units

    def check(self, text: str) -> GateReport:
        report = GateReport(passed=True)
        # 검사 단위마다 '숫자가 있으면 근거 ID도 있어야 한다'
        for sent in self._split_units(text):
            # 근거 태그·날짜·ID 는 숫자로 세지 않습니다
            scannable = _IGNORE_CONTEXT.sub(" ", sent)
            numbers = NUMBER_PATTERN.findall(scannable)
            if not numbers:
                continue
            report.checked_numbers += len(numbers)
            tags = EVIDENCE_TAG.findall(sent)
            if tags:
                report.cited_numbers += len(numbers)
                for t in tags:
                    if self.known and t not in self.known:
                        report.unknown_evidence_ids.append(t)
            else:
                snippet = sent.strip()[:80]
                report.offenders.append(snippet)

        if report.offenders or report.unknown_evidence_ids:
            report.passed = False
        return report

    def enforce(self, text: str) -> str:
        """통과하면 원문을 그대로, 실패하면 예외를 던집니다."""
        rep = self.check(text)
        if not rep.passed and self.strict:
            raise EvidenceMissing(rep.offenders + rep.unknown_evidence_ids, text)
        return text
