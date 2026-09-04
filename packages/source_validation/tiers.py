"""소스 신뢰 등급 (Tier S ~ E).

프로젝트 원칙 §24
    낮은 등급 = 무조건 버림  이 아닙니다.
    레딧 소문도 '조사 시작점(DISCOVERY LEAD)'으로는 가치가 있습니다.
    다만 확정 사실이 되려면 고품질 독립 출처의 검증이 필요합니다.

등급 규칙은 config/source_tiers/default.yaml 에서 바꿀 수 있습니다.
코드에 하드코딩하지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from packages.shared.yamlio import load_file


class SourceTier(str, Enum):
    S = "S"   # SEC, FDA, 정부, 거래소, 공시
    A = "A"   # 주요 언론, 공식 IR, 어닝콜
    B = "B"   # 산업 전문매체
    C = "C"   # 애널리스트 코멘터리
    D = "D"   # 블로그, Substack
    E = "E"   # 레딧, X, 익명
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TierRule:
    weight: float
    can_confirm_fact: bool


_DEFAULT_RULES: dict[SourceTier, TierRule] = {
    SourceTier.S: TierRule(1.00, True),
    SourceTier.A: TierRule(0.80, True),
    SourceTier.B: TierRule(0.60, True),
    SourceTier.C: TierRule(0.40, False),
    SourceTier.D: TierRule(0.20, False),
    SourceTier.E: TierRule(0.05, False),
    SourceTier.UNKNOWN: TierRule(0.10, False),
}

# 도메인 → 등급. config 파일이 있으면 그쪽이 우선입니다.
_DEFAULT_DOMAINS: dict[str, SourceTier] = {
    "sec.gov": SourceTier.S,
    "fda.gov": SourceTier.S,
    "clinicaltrials.gov": SourceTier.S,
    "federalreserve.gov": SourceTier.S,
    "nasdaq.com": SourceTier.S,
    "nyse.com": SourceTier.S,
    "dart.fss.or.kr": SourceTier.S,
    "krx.co.kr": SourceTier.S,
    "twse.com.tw": SourceTier.S,
    "reuters.com": SourceTier.A,
    "bloomberg.com": SourceTier.A,
    "wsj.com": SourceTier.A,
    "ft.com": SourceTier.A,
    "apnews.com": SourceTier.A,
    "cnbc.com": SourceTier.A,
    "semianalysis.com": SourceTier.B,
    "tomshardware.com": SourceTier.B,
    "anandtech.com": SourceTier.B,
    "fiercebiotech.com": SourceTier.B,
    "endpts.com": SourceTier.B,
    "seekingalpha.com": SourceTier.C,
    "substack.com": SourceTier.D,
    "medium.com": SourceTier.D,
    "reddit.com": SourceTier.E,
    "x.com": SourceTier.E,
    "twitter.com": SourceTier.E,
    "stocktwits.com": SourceTier.E,
}

_loaded: dict | None = None


def _load_config(config_dir: Path | None = None) -> dict:
    global _loaded
    if _loaded is not None:
        return _loaded
    _loaded = {"domains": dict(_DEFAULT_DOMAINS), "rules": dict(_DEFAULT_RULES)}
    if config_dir is None:
        return _loaded
    path = config_dir / "source_tiers" / "default.yaml"
    if not path.exists():
        return _loaded
    try:
        raw = load_file(path) or {}
        for tier_name, spec in (raw.get("tiers") or {}).items():
            try:
                t = SourceTier(tier_name)
            except ValueError:
                continue
            _loaded["rules"][t] = TierRule(
                weight=float(spec.get("weight", 0.1)),
                can_confirm_fact=bool(spec.get("can_confirm_fact", False)),
            )
            for dom in spec.get("domains", []) or []:
                _loaded["domains"][dom.lower()] = t
    except Exception:
        # 설정이 깨져도 시스템은 기본값으로 계속 돌아야 합니다.
        pass
    return _loaded


def tier_of_domain(url_or_domain: str, config_dir: Path | None = None) -> SourceTier:
    cfg = _load_config(config_dir)
    host = url_or_domain.lower().strip()
    if "://" in host:
        host = urlparse(host).netloc
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    domains: dict[str, SourceTier] = cfg["domains"]
    if host in domains:
        return domains[host]
    # 서브도메인 처리: news.reuters.com → reuters.com
    parts = host.split(".")
    for i in range(1, len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in domains:
            return domains[cand]
    return SourceTier.UNKNOWN


def rule_of(tier: SourceTier, config_dir: Path | None = None) -> TierRule:
    return _load_config(config_dir)["rules"].get(tier, _DEFAULT_RULES[SourceTier.UNKNOWN])
