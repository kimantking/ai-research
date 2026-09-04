"""레지스트리 로더 + 라우터.

★ 중요 (§29, §62)
   프로필은 100개 넘게 있어도, 하나의 리서치 작업에서
   깨우는 에이전트는 소수입니다. 전부 깨우면 비용이 폭발합니다.
   Router 가 그 문지기 역할을 합니다.
"""

from __future__ import annotations

from pathlib import Path

from packages.shared.yamlio import load_file

from .models import AgentProfile, AgentStatus, Role


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}

    # ------------------------------------------------------------------ 로딩
    @classmethod
    def from_config(cls, config_dir: Path) -> "AgentRegistry":
        reg = cls()
        agents_dir = config_dir / "agents"
        if not agents_dir.exists():
            return reg
        for path in sorted(agents_dir.glob("*.y*ml")):
            raw = load_file(path) or {}
            items = raw.get("agents") if isinstance(raw, dict) and "agents" in raw else [raw]
            for item in items or []:
                if not item:
                    continue
                try:
                    reg.add(AgentProfile.parse(item))
                except Exception as exc:
                    raise ValueError(f"{path.name} 의 에이전트 정의 오류: {exc}") from exc
        return reg

    def add(self, profile: AgentProfile) -> None:
        if profile.id in self._agents:
            raise ValueError(f"에이전트 ID 중복: {profile.id}")
        self._agents[profile.id] = profile

    # ------------------------------------------------------------------ 조회
    def get(self, agent_id: str) -> AgentProfile | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentProfile]:
        return list(self._agents.values())

    def active(self) -> list[AgentProfile]:
        return [a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]

    def by_sector(self, sector: str) -> list[AgentProfile]:
        return [a for a in self._agents.values() if a.sector == sector]

    def by_role(self, role: Role) -> list[AgentProfile]:
        return [a for a in self._agents.values() if a.role == role]

    def departments(self) -> list[str]:
        return sorted({a.department for a in self._agents.values()})

    def sectors(self) -> list[str]:
        return sorted({a.sector for a in self._agents.values() if a.sector})

    def counts(self) -> dict:
        out = {"total": len(self._agents)}
        for st in AgentStatus:
            out[st.value.lower()] = sum(1 for a in self._agents.values() if a.status == st)
        return out


class Router:
    """작업에 필요한 에이전트만 고릅니다."""

    # 섹터와 무관하게 항상 참여하는 공유 전문가
    ALWAYS_ON_ROLES = (
        Role.DATA_QUALITY,
        Role.SOURCE_VERIFICATION,
        Role.TECHNICAL_MASTER,
    )

    def __init__(self, registry: AgentRegistry, max_agents: int = 8):
        self.registry = registry
        # ★ 안전장치: 한 작업에서 이 수를 넘겨 깨우지 않습니다.
        #    "실수로 100명 전부 깨워서 API 비용 폭발" 을 코드로 막습니다.
        self.max_agents = max_agents

    def select_for_research(self, sector: str) -> list[AgentProfile]:
        chosen: dict[str, AgentProfile] = {}

        for a in self.registry.by_sector(sector):
            if a.status == AgentStatus.ACTIVE:
                chosen[a.id] = a

        for role in self.ALWAYS_ON_ROLES:
            for a in self.registry.by_role(role):
                if a.status == AgentStatus.ACTIVE:
                    chosen[a.id] = a

        selected = list(chosen.values())
        if len(selected) > self.max_agents:
            # 섹터 담당 → 공유 전문가 순으로 잘라냅니다
            priority = {
                Role.SECTOR_LEAD: 0, Role.BULL_RESEARCHER: 1, Role.BEAR_RESEARCHER: 1,
                Role.TECHNICAL_MASTER: 2, Role.SOURCE_VERIFICATION: 3, Role.DATA_QUALITY: 3,
            }
            selected.sort(key=lambda a: priority.get(a.role, 9))
            selected = selected[: self.max_agents]
        return selected

    def wake_count_guard(self, agents: list[AgentProfile]) -> None:
        if len(agents) > self.max_agents:
            raise RuntimeError(
                f"한 번에 {len(agents)}명을 깨우려 했습니다 (상한 {self.max_agents}). "
                "비용 폭발 방지를 위해 차단합니다."
            )
