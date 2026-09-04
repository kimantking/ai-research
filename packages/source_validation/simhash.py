"""SimHash — 근사 중복 탐지.

왜 필요한가 (프로젝트 원칙 §23)
    로이터 기사 하나를 50개 사이트가 복사합니다.
    사이트마다 문단이 조금씩 달라서 '정확히 같은 해시'로는 안 잡힙니다.
    그런데 이걸 못 잡으면 시스템은 "50개 출처가 확인했다"고 착각합니다.
    실제 독립 근거는 1개입니다.

    SimHash 는 내용이 비슷하면 해시도 비슷해지는 성질이 있어서,
    해밍 거리로 '거의 같은 문서'를 잡아냅니다.
"""

from __future__ import annotations

import hashlib
import re

_TOKEN_RE = re.compile(r"[0-9a-zA-Z가-힣]+")
HASH_BITS = 64


def _tokens(text: str, shingle: int = 3) -> list[str]:
    """단어 3개씩 묶은 shingle. 문장 순서까지 반영됩니다."""
    words = _TOKEN_RE.findall(text.lower())
    if len(words) < shingle:
        return words
    return [" ".join(words[i : i + shingle]) for i in range(len(words) - shingle + 1)]


def simhash(text: str, shingle: int = 3) -> int:
    """텍스트의 64비트 SimHash."""
    vector = [0] * HASH_BITS
    toks = _tokens(text, shingle)
    if not toks:
        return 0
    for tok in toks:
        h = int.from_bytes(hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest(), "big")
        for i in range(HASH_BITS):
            vector[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(HASH_BITS):
        if vector[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    """두 해시의 다른 비트 수. 작을수록 비슷한 문서."""
    return bin(a ^ b).count("1")


def is_near_duplicate(a: int, b: int, threshold: int = 8) -> bool:
    """64비트 중 8비트 이하로 다르면 사실상 같은 문서로 봅니다."""
    return hamming(a, b) <= threshold


def content_hash(text: str) -> str:
    """정확 일치용 해시 (공백/대소문자 정규화 후)."""
    normalized = " ".join(_TOKEN_RE.findall(text.lower()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
