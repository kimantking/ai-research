"""Agent Reach 어댑터.

Agent Reach 는 AI 에이전트에게 인터넷 접근을 주는 외부 CLI 도구입니다.
(https://github.com/Panniantong/agent-reach — MIT)

★ 이 어댑터가 지키는 규칙 (docs/AGENT_REACH.md)

  1. **절대 자동 설치하지 않습니다.**
     설치는 자격증명(쿠키·API 키)이 걸린 행위이므로 사용자 승인 사항입니다.
     설치되어 있지 않으면 NOT_INSTALLED 를 돌려주고 조용히 비활성화됩니다.

  2. **Agent Reach 의 판정을 신뢰하지 않습니다.**
     가져온 문서는 전부 `verified=False` 로 표시되고,
     Research Firewall 을 통과해야만 에이전트에게 도달합니다.
     레딧에서 가져왔으면 여전히 Tier E 입니다.

  3. **쿠키가 필요한 채널은 기본 비활성입니다.**
     Twitter / Instagram / LinkedIn / 샤오홍슈 등은 세션 쿠키를 저장해야 하고,
     대부분 플랫폼 약관 위반 + 계정 정지 위험이 있습니다.
     `config/data_sources/agent_reach.yaml` 에서 명시적으로 켜야 합니다.

  4. **타임아웃과 출력 크기에 상한을 둡니다.**
     외부 프로세스가 멈추거나 거대한 출력을 뱉어도 우리가 멈추지 않게.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from packages.shared.logging import get_logger
from packages.shared.yamlio import load_file

from .base import CollectorHealth, CollectorStatus, SourceDocument

log = get_logger("agent_reach")

# 외부 프로세스 출력 상한 (8MB). 넘으면 잘라냅니다.
MAX_OUTPUT_BYTES = 8 * 1024 * 1024

# 자격증명이 필요 없는 채널 — 기본 허용
ZERO_CONFIG_CHANNELS = {"web", "rss", "youtube", "github", "hackernews"}

# 세션 쿠키가 필요한 채널 — 기본 차단
COOKIE_CHANNELS = {
    "twitter", "x", "instagram", "linkedin", "facebook",
    "xiaohongshu", "xhs", "bilibili", "xueqiu", "xiaoyuzhou",
}


class AgentReachCollector:
    collector_id = "agent_reach"

    def __init__(self, config_dir: Path | None = None,
                 executable: str | None = None):
        self.config_dir = config_dir
        self._exe = executable
        self._cfg = self._load_config()

    # ------------------------------------------------------------------ 설정
    def _load_config(self) -> dict:
        default = {
            "enabled": True,
            "auto_install": False,          # ★ 절대 True 로 바꾸지 마십시오
            "allow_cookie_channels": False,
            "enabled_channels": sorted(ZERO_CONFIG_CHANNELS),
            "read_timeout_seconds": 30,
            "search_timeout_seconds": 60,
            "max_results": 10,
        }
        if self.config_dir is None:
            return default
        raw = load_file(self.config_dir / "data_sources" / "agent_reach.yaml")
        if isinstance(raw, dict):
            default.update({k: v for k, v in raw.items() if v is not None})
        return default

    # ------------------------------------------------------------------ 탐지
    def find_executable(self) -> str | None:
        """agent-reach 실행 파일을 찾습니다. 설치는 하지 않습니다."""
        if self._exe:
            return self._exe if Path(self._exe).exists() or shutil.which(self._exe) else None

        found = shutil.which("agent-reach")
        if found:
            return found

        # 흔한 설치 위치 (pipx / venv), Windows 와 POSIX 모두
        home = Path.home()
        candidates = [
            home / ".local" / "bin" / "agent-reach",
            home / ".agent-reach-venv" / "bin" / "agent-reach",
            home / ".agent-reach-venv" / "Scripts" / "agent-reach.exe",
            home / ".local" / "bin" / "agent-reach.exe",
            home / "AppData" / "Roaming" / "Python" / "Scripts" / "agent-reach.exe",
            home / "pipx" / "venvs" / "agent-reach" / "Scripts" / "agent-reach.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    # ------------------------------------------------------------------ 상태
    def health(self) -> CollectorHealth:
        install_hint = (
            "설치하지 않아도 시스템은 정상 동작합니다. "
            "설치하시려면: .\\scripts\\install-agent-reach.ps1 "
            "(자격증명이 필요하므로 사용자 승인 사항입니다)"
        )

        if not self._cfg.get("enabled", True):
            return CollectorHealth(
                self.collector_id, "Agent Reach", CollectorStatus.DISABLED,
                "설정에서 비활성화되어 있습니다 (config/data_sources/agent_reach.yaml)",
                install_hint=install_hint,
            )

        exe = self.find_executable()
        if not exe:
            return CollectorHealth(
                self.collector_id, "Agent Reach", CollectorStatus.NOT_INSTALLED,
                "설치되어 있지 않습니다. 이것은 오류가 아닙니다 — "
                "Agent Reach 없이도 시스템 전체가 정상 동작합니다.",
                channels_available=[],
                channels_need_auth=sorted(COOKIE_CHANNELS),
                install_hint=install_hint,
            )

        version, detail = "", ""
        try:
            out = self._run([exe, "--version"], timeout=15)
            version = (out or "").strip().splitlines()[0][:80] if out else ""
        except Exception as exc:
            detail = f"버전 확인 실패: {exc}"

        allowed = self._allowed_channels()
        return CollectorHealth(
            self.collector_id, "Agent Reach", CollectorStatus.CONNECTED,
            detail or "사용 가능. 수집 결과는 Research Firewall 을 통과해야 합니다.",
            version=version,
            channels_available=allowed,
            channels_need_auth=sorted(COOKIE_CHANNELS - set(allowed)),
            install_hint="",
        )

    def doctor(self) -> str:
        """agent-reach 자체 진단을 그대로 돌려줍니다."""
        exe = self.find_executable()
        if not exe:
            return "agent-reach 가 설치되어 있지 않습니다."
        try:
            return self._run([exe, "doctor"], timeout=60) or "(출력 없음)"
        except Exception as exc:
            return f"doctor 실행 실패: {exc}"

    # ------------------------------------------------------------------ 채널
    def _allowed_channels(self) -> list[str]:
        configured = set(self._cfg.get("enabled_channels") or [])
        allowed = configured & ZERO_CONFIG_CHANNELS
        if self._cfg.get("allow_cookie_channels"):
            allowed |= (configured & COOKIE_CHANNELS)
        return sorted(allowed)

    def channel_allowed(self, channel: str) -> tuple[bool, str]:
        ch = (channel or "web").lower()
        if ch in self._allowed_channels():
            return True, ""
        if ch in COOKIE_CHANNELS:
            return False, (
                f"'{ch}' 채널은 세션 쿠키가 필요합니다. 대부분 플랫폼 약관 위반이며 "
                "계정 정지 위험이 있어 기본 차단되어 있습니다. "
                "config/data_sources/agent_reach.yaml 에서 명시적으로 켜야 합니다."
            )
        return False, f"'{ch}' 채널이 설정에 없습니다."

    # ------------------------------------------------------------------ 수집
    def read(self, url: str, timeout: float | None = None) -> SourceDocument | None:
        """URL 한 건을 읽습니다. 실패하면 None (예외를 던지지 않습니다)."""
        exe = self.find_executable()
        if not exe:
            return None
        timeout = timeout or float(self._cfg.get("read_timeout_seconds", 30))
        try:
            out = self._run([exe, "read", url, "--json"], timeout=timeout)
        except Exception as exc:
            log.warning("agent_reach_read_failed", url=url, error=str(exc))
            return None
        if not out:
            return None
        return self._to_document(out, url=url, channel="web")

    def search(self, query: str, channel: str = "web",
               limit: int | None = None,
               timeout: float | None = None) -> list[SourceDocument]:
        exe = self.find_executable()
        if not exe:
            return []

        ok, why = self.channel_allowed(channel)
        if not ok:
            log.info("agent_reach_channel_blocked", channel=channel, reason=why)
            return []

        limit = int(limit or self._cfg.get("max_results", 10))
        timeout = timeout or float(self._cfg.get("search_timeout_seconds", 60))
        try:
            out = self._run(
                [exe, "search", query, "--channel", channel,
                 "--limit", str(limit), "--json"],
                timeout=timeout,
            )
        except Exception as exc:
            log.warning("agent_reach_search_failed", channel=channel, error=str(exc))
            return []
        if not out:
            return []

        docs: list[SourceDocument] = []
        for item in self._parse_items(out):
            doc = self._item_to_document(item, channel)
            if doc:
                docs.append(doc)
        return docs[:limit]

    # ------------------------------------------------------------------ 내부
    def _run(self, cmd: list[str], timeout: float) -> str | None:
        """외부 프로세스 실행. 상속되는 환경에서 시크릿을 지웁니다."""
        env = dict(os.environ)
        for key in list(env):
            if any(s in key.upper() for s in
                   ("ANTHROPIC", "OPENAI", "GOOGLE_API", "POSTGRES", "DATABASE_URL")):
                env.pop(key, None)

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=env, check=False,
        )
        if proc.returncode != 0:
            log.warning("agent_reach_nonzero_exit",
                        code=proc.returncode,
                        stderr=(proc.stderr or "")[:300])
            return None
        out = proc.stdout or ""
        if len(out.encode("utf-8", "ignore")) > MAX_OUTPUT_BYTES:
            log.warning("agent_reach_output_truncated", bytes=len(out))
            out = out[: MAX_OUTPUT_BYTES // 4]
        return out

    @staticmethod
    def _parse_items(out: str) -> list[dict]:
        """JSON 또는 JSON Lines 를 모두 받아들입니다."""
        out = out.strip()
        if not out:
            return []
        try:
            data = json.loads(out)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
            if isinstance(data, dict):
                for key in ("results", "items", "data", "documents"):
                    v = data.get(key)
                    if isinstance(v, list):
                        return [d for d in v if isinstance(d, dict)]
                return [data]
        except json.JSONDecodeError:
            pass
        items: list[dict] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    items.append(obj)
            except json.JSONDecodeError:
                continue
        return items

    def _to_document(self, out: str, url: str, channel: str) -> SourceDocument | None:
        items = self._parse_items(out)
        if not items:
            # JSON 이 아니면 본문 텍스트로 간주
            text = out.strip()
            if not text:
                return None
            return SourceDocument(
                url=url, body=text, domain=_domain_of(url),
                channel=channel, collector=self.collector_id, verified=False,
            )
        return self._item_to_document(items[0], channel, fallback_url=url)

    def _item_to_document(self, item: dict, channel: str,
                          fallback_url: str = "") -> SourceDocument | None:
        url = str(item.get("url") or item.get("link") or fallback_url or "").strip()
        body = str(item.get("content") or item.get("text")
                   or item.get("body") or item.get("summary") or "")
        title = str(item.get("title") or item.get("name") or "")
        if not url and not body:
            return None
        return SourceDocument(
            url=url,
            title=title[:500],
            body=body,
            domain=_domain_of(url),
            channel=channel,
            published=_parse_time(item.get("published")
                                  or item.get("date")
                                  or item.get("created_at")),
            author=str(item.get("author") or item.get("user") or "")[:200],
            collector=self.collector_id,
            # ★ 항상 미검증. Research Firewall 이 판정합니다.
            verified=False,
        )


# ====================================================================== 유틸


def _domain_of(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url if "://" in url else "https://" + url).netloc
        return host.split(":")[0].removeprefix("www.").lower()
    except ValueError:
        return ""


def _parse_time(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    for parse in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
        lambda t: datetime.strptime(t, "%Y/%m/%d"),
        lambda t: datetime.strptime(t, "%a, %d %b %Y %H:%M:%S %z"),
    ):
        try:
            dt = parse(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None
