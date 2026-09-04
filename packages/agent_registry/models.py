"""에이전트 프로필 스키마.

★ 의존성 없음 (표준 라이브러리만)
   pydantic 이 설치되지 않아도 핵심 로직 전체가 동작해야 합니다.
   외부 패키지는 API 계층에서만 씁니다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"          # 지금 일함
    REGISTERED = "REGISTERED"  # 정의만 되어 있음 (LLM 호출 없음)
    SLEEPING = "SLEEPING"      # 깨우면 일함


class Role(str, Enum):
    CIO = "CIO"
    CHIEF_LEARNING_OFFICER = "CHIEF_LEARNING_OFFICER"
    SECTOR_LEAD = "SECTOR_LEAD"
    BULL_RESEARCHER = "BULL_RESEARCHER"
    BEAR_RESEARCHER = "BEAR_RESEARCHER"
    TECHNICAL_MASTER = "TECHNICAL_MASTER"
    TECHNICAL_BULL = "TECHNICAL_BULL"
    TECHNICAL_BEAR = "TECHNICAL_BEAR"
    TECHNICAL_JUDGE = "TECHNICAL_JUDGE"
    FUNDAMENTAL_MASTER = "FUNDAMENTAL_MASTER"
    VALUATION_MASTER = "VALUATION_MASTER"
    QUANT_MASTER = "QUANT_MASTER"
    MACRO_EXPERT = "MACRO_EXPERT"
    RISK_EXPERT = "RISK_EXPERT"
    DATA_QUALITY = "DATA_QUALITY"
    SOURCE_VERIFICATION = "SOURCE_VERIFICATION"
    EVIDENCE_JUDGE = "EVIDENCE_JUDGE"
    RED_TEAM = "RED_TEAM"
    INVESTMENT_COMMITTEE = "INVESTMENT_COMMITTEE"
    SPECIALIST = "SPECIALIST"


class ModelTier(str, Enum):
    """실제 모델명을 프로필에 박지 않습니다 (모델 독립성, §51).

    등급 → 실제 모델 매핑은 config/models.yaml 한 곳에서만 합니다.
    """

    STRONG = "tier_strong"
    MID = "tier_mid"
    CHEAP = "tier_cheap"
    CODE_ONLY = "code_only"   # LLM 을 아예 안 씀


@dataclass
class ModelPolicy:
    default: ModelTier = ModelTier.MID
    cheap_tasks: ModelTier = ModelTier.CHEAP

    @classmethod
    def parse(cls, raw) -> "ModelPolicy":
        if raw is None:
            return cls()
        if isinstance(raw, ModelPolicy):
            return raw
        return cls(
            default=ModelTier(raw.get("default", "tier_mid")),
            cheap_tasks=ModelTier(raw.get("cheap_tasks", "tier_cheap")),
        )

    def to_dict(self) -> dict:
        return {"default": self.default.value, "cheap_tasks": self.cheap_tasks.value}


@dataclass
class AgentProfile:
    id: str
    name: str
    department: str
    role: Role
    sector: str | None = None
    status: AgentStatus = AgentStatus.REGISTERED

    specialties: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    model_policy: ModelPolicy = field(default_factory=ModelPolicy)
    research_depth: int = 10
    learning_target_minutes: int = 240
    source_permissions: list[str] = field(
        default_factory=lambda: ["S", "A", "B", "C", "D", "E"]
    )
    memory_namespace: str = ""

    # 픽셀 사무실에서의 기본 자리
    home_location: str = "office_floor"

    # Bull 은 상승 쪽, Bear 는 하락 쪽으로 약간 기울어 시작합니다.
    # 편향이 아니라 역할 분담이며, 틀리면 데이터가 교정합니다.
    role_prior: float = 0.0

    # ------------------------------------------------------------------
    @classmethod
    def parse(cls, raw: dict) -> "AgentProfile":
        """YAML 한 덩어리를 프로필로 변환. 잘못된 값은 명확한 오류를 냅니다."""
        missing = [k for k in ("id", "name", "department", "role") if not raw.get(k)]
        if missing:
            raise ValueError(f"필수 항목 누락: {', '.join(missing)}")

        try:
            role = Role(raw["role"])
        except ValueError:
            raise ValueError(f"알 수 없는 role: {raw['role']}") from None
        try:
            status = AgentStatus(raw.get("status", "REGISTERED"))
        except ValueError:
            raise ValueError(f"알 수 없는 status: {raw.get('status')}") from None

        depth = int(raw.get("research_depth", 10))
        if not 1 <= depth <= 10:
            raise ValueError(f"research_depth 는 1~10 이어야 합니다: {depth}")

        prior = float(raw.get("role_prior", 0.0))
        if not -1.0 <= prior <= 1.0:
            raise ValueError(f"role_prior 는 -1.0~1.0 이어야 합니다: {prior}")

        agent_id = str(raw["id"])
        return cls(
            id=agent_id,
            name=str(raw["name"]),
            department=str(raw["department"]),
            role=role,
            sector=raw.get("sector") or None,
            status=status,
            specialties=list(raw.get("specialties") or []),
            skills=list(raw.get("skills") or []),
            model_policy=ModelPolicy.parse(raw.get("model_policy")),
            research_depth=depth,
            learning_target_minutes=int(raw.get("learning_target_minutes", 240)),
            source_permissions=list(
                raw.get("source_permissions") or ["S", "A", "B", "C", "D", "E"]
            ),
            memory_namespace=raw.get("memory_namespace") or f"agents/{agent_id}",
            home_location=raw.get("home_location") or "office_floor",
            role_prior=prior,
        )

    def __post_init__(self):
        if not self.memory_namespace:
            self.memory_namespace = f"agents/{self.id}"

    @property
    def is_awake(self) -> bool:
        return self.status == AgentStatus.ACTIVE

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["status"] = self.status.value
        d["model_policy"] = self.model_policy.to_dict()
        return d
