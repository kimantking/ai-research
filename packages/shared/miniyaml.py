"""YAML 최소 파서 (표준 라이브러리만).

★ 왜 이런 게 있는가
   이 프로젝트는 "아무것도 설치되지 않은 상태에서도 일단 돌아가야 한다"를
   목표로 합니다. PyYAML 이 있으면 그걸 쓰고, 없으면 이걸 씁니다.

★ 지원 범위 (우리 config/*.yaml 이 쓰는 문법에 한정)
   - 중첩 매핑, 리스트, 리스트 안의 매핑
   - 스칼라: 문자열, 정수, 실수, true/false, null/~, 인용 문자열
   - 인라인 리스트 [a, b, c]
   - 주석 (#), 문서 구분자 (---)
   지원하지 않음: 앵커/별칭, 멀티라인 블록(|, >), 복합 키, 흐름 매핑 {}

   지원하지 않는 문법을 만나면 조용히 틀리는 대신 예외를 던집니다.
   (조용히 틀린 설정만큼 위험한 건 없습니다)
"""

from __future__ import annotations

import re
from typing import Any

_NUM_INT = re.compile(r"^[+-]?\d+$")
_NUM_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


class MiniYamlError(ValueError):
    pass


def _scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "" or s in ("null", "~", "Null", "NULL"):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if _NUM_INT.match(s):
        return int(s)
    if _NUM_FLOAT.match(s):
        return float(s)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in _split_inline(inner)]
    if s.startswith("{") and s.endswith("}"):
        raise MiniYamlError(f"흐름 매핑 {{...}} 은 지원하지 않습니다: {s}")
    if s in ("|", ">") or s.startswith("|") or s.startswith(">"):
        raise MiniYamlError(f"멀티라인 블록 스칼라는 지원하지 않습니다: {s}")
    return s


def _split_inline(text: str) -> list[str]:
    """[a, "b, c", d] 처럼 따옴표 안의 콤마를 보호하며 분리."""
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip() != ""]


def _strip_comment(line: str) -> str:
    """따옴표 밖의 # 부터 주석으로 처리."""
    out: list[str] = []
    quote: str | None = None
    prev_space = True
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            prev_space = False
            continue
        if ch == "#" and (i == 0 or prev_space):
            break
        out.append(ch)
        prev_space = ch in " \t"
    return "".join(out).rstrip()


class _Line:
    __slots__ = ("indent", "text", "no")

    def __init__(self, indent: int, text: str, no: int):
        self.indent = indent
        self.text = text
        self.no = no


def _tokenize(src: str) -> list[_Line]:
    lines: list[_Line] = []
    for i, raw in enumerate(src.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise MiniYamlError(f"{i}행: 들여쓰기에 탭을 쓸 수 없습니다")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        if stripped.strip() in ("---", "..."):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append(_Line(indent, stripped.strip(), i))
    return lines


def _parse_block(lines: list[_Line], pos: int, indent: int) -> tuple[Any, int]:
    if pos >= len(lines):
        return None, pos

    if lines[pos].text.startswith("- "):
        return _parse_list(lines, pos, indent)
    if lines[pos].text == "-":
        return _parse_list(lines, pos, indent)
    return _parse_map(lines, pos, indent)


def _parse_list(lines: list[_Line], pos: int, indent: int) -> tuple[list, int]:
    out: list = []
    while pos < len(lines):
        ln = lines[pos]
        if ln.indent < indent or not (ln.text == "-" or ln.text.startswith("- ")):
            break
        if ln.indent > indent:
            raise MiniYamlError(f"{ln.no}행: 리스트 들여쓰기가 어긋났습니다")

        rest = ln.text[1:].strip() if ln.text != "-" else ""
        pos += 1

        if rest == "":
            # 다음 줄부터가 이 항목의 내용
            if pos < len(lines) and lines[pos].indent > indent:
                value, pos = _parse_block(lines, pos, lines[pos].indent)
                out.append(value)
            else:
                out.append(None)
            continue

        # "- key: value" 형태 → 매핑 항목의 첫 줄
        key_match = re.match(r"^([^:\s][^:]*):\s*(.*)$", rest)
        if key_match:
            item_indent = ln.indent + 2
            synthetic = [_Line(item_indent, rest, ln.no)]
            while pos < len(lines) and lines[pos].indent > ln.indent:
                synthetic.append(lines[pos])
                pos += 1
            value, _ = _parse_map(synthetic, 0, item_indent)
            out.append(value)
        else:
            out.append(_scalar(rest))
    return out, pos


def _parse_map(lines: list[_Line], pos: int, indent: int) -> tuple[dict, int]:
    out: dict = {}
    while pos < len(lines):
        ln = lines[pos]
        if ln.indent < indent:
            break
        if ln.indent > indent:
            raise MiniYamlError(f"{ln.no}행: 예상보다 깊은 들여쓰기")
        if ln.text.startswith("- "):
            break

        m = re.match(r"^([^:]+):\s*(.*)$", ln.text)
        if not m:
            raise MiniYamlError(f"{ln.no}행: 해석할 수 없는 줄 -> {ln.text!r}")
        key_raw, rest = m.group(1).strip(), m.group(2).strip()
        key = _scalar(key_raw)
        if isinstance(key, str) and len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
            key = key[1:-1]
        pos += 1

        if rest != "":
            out[key] = _scalar(rest)
            continue

        if pos < len(lines) and lines[pos].indent > indent:
            value, pos = _parse_block(lines, pos, lines[pos].indent)
            out[key] = value
        elif pos < len(lines) and lines[pos].indent == indent and \
                lines[pos].text.startswith("- "):
            # 같은 들여쓰기의 리스트 (YAML 에서 허용되는 형태)
            value, pos = _parse_list(lines, pos, indent)
            out[key] = value
        else:
            out[key] = None
    return out, pos


def safe_load(src: str) -> Any:
    lines = _tokenize(src)
    if not lines:
        return None
    value, pos = _parse_block(lines, 0, lines[0].indent)
    if pos != len(lines):
        raise MiniYamlError(f"{lines[pos].no}행 이후를 해석하지 못했습니다")
    return value
