"""YAML 읽기 진입점.

PyYAML 이 있으면 그것을, 없으면 내장 miniyaml 을 씁니다.
어느 쪽이 쓰였는지는 BACKEND 로 확인할 수 있습니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - 환경에 따라 갈림
    import yaml as _pyyaml

    BACKEND = "pyyaml"
except ImportError:  # pragma: no cover
    _pyyaml = None
    BACKEND = "miniyaml"

from . import miniyaml


def loads(text: str) -> Any:
    if _pyyaml is not None:
        return _pyyaml.safe_load(text)
    return miniyaml.safe_load(text)


def load_file(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return None
    return loads(p.read_text(encoding="utf-8"))
