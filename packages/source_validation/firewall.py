"""Research Firewall — 검색 결과를 통과시킬지 판정합니다.

프로젝트 원칙 §22
    탐지 대상: SEO 스팸 / 낚시성 제목 / 콘텐츠 팜 / AI 생성 스팸 /
    중복·복사 기사 / 오래된 정보를 최신처럼 위장 / 티커 오인 /
    출처 없는 금융 수치 / 광고성 콘텐츠 / 익명 루머 / 순환 인용

이건 완벽한 필터가 아닙니다. 확실히 걸러야 할 것만 걸러내고,
애매한 것은 '통과시키되 신뢰도를 낮춰서' 넘깁니다.
무엇이든 확신하는 필터가 제일 위험합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .simhash import content_hash, hamming, simhash
from .tiers import SourceTier, rule_of, tier_of_domain

# ------------------------------------------------------------------ 규칙

CLICKBAIT_PATTERNS = [
    r"충격", r"경악", r"소름", r"대박", r"폭등\s*임박", r"지금\s*사야",
    r"you won'?t believe", r"shocking", r"this one trick", r"skyrocket",
    r"to the moon", r"guaranteed (?:profit|return)", r"\d+00% (?:gain|return)",
    r"급등주", r"작전주", r"세력",
]

PROMO_PATTERNS = [
    r"sponsored (?:content|by)", r"paid (?:promotion|advertisement)",
    r"제휴\s*링크", r"광고\s*문의", r"유료\s*광고",
    r"press release distributed", r"이 기사는 보도자료",
]

RUMOR_PATTERNS = [
    r"소식통에 따르면", r"익명의?\s*(?:관계자|소식통)", r"카더라",
    r"rumou?r has it", r"unnamed sources? (?:say|claim)", r"insiders? whisper",
    r"업계\s*관계자는\s*익명",
]

AI_SPAM_PATTERNS = [
    r"as an ai language model", r"in conclusion, it is important to note that",
    r"delve into the (?:world|realm) of", r"in today'?s fast-paced world",
    r"navigating the (?:complex|ever-changing) landscape",
]

# "숫자가 나오는데 출처 표현이 없는" 경우를 찾기 위한 패턴
NUMBER_PATTERN = re.compile(
    r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s*(?:%|퍼센트|억|조|만|billion|million|B|M|배|원|달러)"
)
ATTRIBUTION_PATTERN = re.compile(
    r"(according to|per the|filed with|보고서에 따르면|공시에 따르면|10-[KQ]|8-K|"
    r"사업보고서|분기보고서|SEC|FDA|reported by|출처[:：]|자료[:：])",
    re.IGNORECASE,
)


@dataclass
class FirewallVerdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    tier: SourceTier = SourceTier.UNKNOWN
    confidence: float = 0.0
    can_confirm_fact: bool = False
    is_duplicate_of: str | None = None
    content_hash: str = ""
    simhash: int = 0
    unsourced_numbers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "penalties": self.penalties,
            "tier": self.tier.value,
            "confidence": round(self.confidence, 3),
            "can_confirm_fact": self.can_confirm_fact,
            "is_duplicate_of": self.is_duplicate_of,
            "content_hash": self.content_hash[:16],
            "unsourced_numbers": self.unsourced_numbers[:5],
        }


class ResearchFirewall:
    """읽은 문서를 판정하고, 본 것을 기억해 중복을 잡습니다."""

    def __init__(self, config_dir: Path | None = None, near_dup_threshold: int = 8):
        self.config_dir = config_dir
        self.near_dup_threshold = near_dup_threshold
        self._exact: dict[str, str] = {}      # content_hash -> source_id
        self._sims: list[tuple[int, str]] = []  # (simhash, source_id)

    # ------------------------------------------------------------------
    def check(
        self,
        source_id: str,
        url: str,
        title: str,
        body: str,
        published: datetime | None = None,
        now: datetime | None = None,
        claims_recent: bool = False,
    ) -> FirewallVerdict:
        now = now or datetime.now(timezone.utc)
        text = f"{title}\n{body}"
        v = FirewallVerdict(passed=True)

        # ---- 1) 등급 ----
        v.tier = tier_of_domain(url, self.config_dir)
        rule = rule_of(v.tier, self.config_dir)
        v.confidence = rule.weight
        v.can_confirm_fact = rule.can_confirm_fact

        # ---- 2) 중복 ----
        v.content_hash = content_hash(text)
        v.simhash = simhash(text)

        if v.content_hash in self._exact:
            v.passed = False
            v.is_duplicate_of = self._exact[v.content_hash]
            v.reasons.append(f"정확히 동일한 문서 (원본: {v.is_duplicate_of})")
            return v

        for h, sid in self._sims:
            if hamming(h, v.simhash) <= self.near_dup_threshold:
                v.passed = False
                v.is_duplicate_of = sid
                v.reasons.append(
                    f"근사 중복 — 사실상 같은 기사 (원본: {sid}). "
                    "독립 근거로 세지 않습니다."
                )
                return v

        # ---- 3) 스팸/낚시/광고/루머/AI생성 ----
        low = text.lower()

        def _hits(patterns: list[str]) -> list[str]:
            return [p for p in patterns if re.search(p, low, re.IGNORECASE)]

        clickbait = _hits(CLICKBAIT_PATTERNS)
        promo = _hits(PROMO_PATTERNS)
        rumor = _hits(RUMOR_PATTERNS)
        ai_spam = _hits(AI_SPAM_PATTERNS)

        if clickbait:
            v.penalties.append(f"낚시성 표현 {len(clickbait)}건")
            v.confidence *= 0.35
        if promo:
            v.passed = False
            v.reasons.append("광고/보도자료 배포 콘텐츠")
        if ai_spam:
            v.passed = False
            v.reasons.append("AI 생성 스팸으로 의심되는 정형 문구")
        if rumor:
            v.penalties.append("익명 소식통 기반 서술")
            v.confidence *= 0.4
            v.can_confirm_fact = False

        # ---- 4) 오래된 정보를 최신처럼 ----
        if published is not None:
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age = now - published
            if age > timedelta(days=365 * 2):
                v.penalties.append(f"2년 이상 지난 자료 ({published.date()})")
                v.confidence *= 0.5
            if claims_recent and age > timedelta(days=90):
                v.passed = False
                v.reasons.append(
                    f"최신 정보라고 주장하지만 실제 발행일은 {published.date()}"
                )
        else:
            v.penalties.append("발행일 불명")
            v.confidence *= 0.7

        # ---- 5) 출처 없는 숫자 ----
        numbers = NUMBER_PATTERN.findall(body)
        if numbers and not ATTRIBUTION_PATTERN.search(body):
            v.unsourced_numbers = [n.strip() for n in numbers][:10]
            v.penalties.append(f"출처 표기 없는 수치 {len(numbers)}개")
            v.confidence *= 0.4
            v.can_confirm_fact = False

        # ---- 6) 본문이 너무 짧음 (콘텐츠 팜) ----
        word_count = len(re.findall(r"\S+", body))
        if word_count < 40:
            v.penalties.append(f"본문 과소 ({word_count}단어)")
            v.confidence *= 0.5

        # ---- 통과했으면 기억한다 ----
        if v.passed:
            self._exact[v.content_hash] = source_id
            self._sims.append((v.simhash, source_id))

        v.confidence = max(0.0, min(1.0, v.confidence))
        return v

    def reset(self) -> None:
        self._exact.clear()
        self._sims.clear()
