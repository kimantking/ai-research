"""애플리케이션 설정.

★ 의존성 없음
   pydantic-settings 가 없어도 동작합니다. .env 는 직접 읽습니다.
   시크릿은 오직 이 파일을 통해서만 읽습니다 — 코드 곳곳에서
   os.environ 을 직접 뒤지지 않습니다. 그래야 통제가 됩니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_TRUE = {"1", "true", "yes", "on", "y"}


def parse_env_file(path: Path) -> dict[str, str]:
    """.env 파일을 읽습니다. 없으면 빈 딕셔너리."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


@dataclass
class Settings:
    # ---- 실행 모드 ----
    app_env: str = "development"
    log_level: str = "INFO"
    mock_mode: bool = True

    # ---- 포트 ----
    api_port: int = 8010
    web_port: int = 3010
    postgres_port: int = 5433
    redis_port: int = 6380

    # ---- 접속 문자열 (Phase 5부터) ----
    database_url: str = ""
    redis_url: str = ""
    # ★ Phase 5b — 영속화 (기본 SQLite. 설치·Docker 불필요)
    persistence: str = "sqlite"        # sqlite | off
    sqlite_path: str = "data/airo.db"
    autosave_every_ticks: int = 200
    # ★ Phase 21/12 — 실데이터
    market_provider: str = "csv_file"   # csv_file | stooq | yfinance | off
    market_data_dir: str = "data/market"
    market_exchange: str = "XNYS"
    sec_contact_email: str = ""         # SEC 가 요구합니다(비용 없음)
    # 한국 데이터 (둘 다 무료 키)
    data_go_kr_key: str = ""            # 공공데이터포털 금융위 주식시세
    dart_api_key: str = ""              # 금융감독원 전자공시

    # ---- LLM (Phase 10부터. 없으면 MOCK 으로 동작) ----
    llm_enabled: bool = False
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    daily_llm_budget_usd: float = 5.0

    # ---- 데이터 소스 ----
    sec_user_agent: str = "AI Stock Research Office contact@example.com"
    market_data_provider: str = "mock"

    project_root: Path = field(default=PROJECT_ROOT)

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        root = root or PROJECT_ROOT
        values = parse_env_file(root / ".env")
        # 실제 환경변수가 .env 보다 우선합니다 (Docker/CI 대응)
        def get(key: str, default: str) -> str:
            return os.environ.get(key.upper(), values.get(key.upper(), default))

        def as_int(key: str, default: int) -> int:
            try:
                return int(get(key, str(default)))
            except ValueError:
                return default

        def as_float(key: str, default: float) -> float:
            try:
                return float(get(key, str(default)))
            except ValueError:
                return default

        def as_bool(key: str, default: bool) -> bool:
            return get(key, "true" if default else "false").strip().lower() in _TRUE

        return cls(
            app_env=get("APP_ENV", "development"),
            log_level=get("LOG_LEVEL", "INFO"),
            mock_mode=as_bool("MOCK_MODE", True),
            api_port=as_int("API_PORT", 8010),
            web_port=as_int("WEB_PORT", 3010),
            postgres_port=as_int("POSTGRES_PORT", 5433),
            redis_port=as_int("REDIS_PORT", 6380),
            database_url=get("DATABASE_URL", ""),
            redis_url=get("REDIS_URL", ""),
            persistence=get("PERSISTENCE", "sqlite").strip().lower(),
            sqlite_path=get("SQLITE_PATH", "data/airo.db"),
            autosave_every_ticks=as_int("AUTOSAVE_EVERY_TICKS", 200),
            market_provider=get("MARKET_PROVIDER", "csv_file").strip().lower(),
            market_data_dir=get("MARKET_DATA_DIR", "data/market"),
            market_exchange=get("MARKET_EXCHANGE", "XNYS").strip().upper(),
            sec_contact_email=get("SEC_CONTACT_EMAIL", "").strip(),
            data_go_kr_key=get("DATA_GO_KR_KEY", "").strip(),
            dart_api_key=get("DART_API_KEY", "").strip(),
            llm_enabled=as_bool("LLM_ENABLED", False),
            anthropic_api_key=get("ANTHROPIC_API_KEY", ""),
            openai_api_key=get("OPENAI_API_KEY", ""),
            google_api_key=get("GOOGLE_API_KEY", ""),
            daily_llm_budget_usd=as_float("DAILY_LLM_BUDGET_USD", 5.0),
            sec_user_agent=get(
                "SEC_USER_AGENT", "AI Stock Research Office contact@example.com"
            ),
            market_data_provider=get("MARKET_DATA_PROVIDER", "mock"),
            project_root=root,
        )

    # ------------------------------------------------------------------
    @property
    def config_dir(self) -> Path:
        return self.project_root / "config"

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    @property
    def static_dir(self) -> Path:
        return self.project_root / "services" / "api" / "static"

    @property
    def llm_available(self) -> bool:
        """실제 LLM 을 호출할 수 있는 상태인지."""
        return self.llm_enabled and bool(
            self.anthropic_api_key or self.openai_api_key or self.google_api_key
        )

    def public_dict(self) -> dict:
        """★ 시크릿은 절대 담지 않습니다. 상태만 알려줍니다."""
        return {
            "app_env": self.app_env,
            "mock_mode": self.mock_mode,
            "persistence": self.persistence,
            "market_provider": self.market_provider,
            "market_exchange": self.market_exchange,
            "sec_contact_email_set": bool(self.sec_contact_email),
            "data_go_kr_key_set": bool(self.data_go_kr_key),
            "dart_api_key_set": bool(self.dart_api_key),
            "api_port": self.api_port,
            "web_port": self.web_port,
            "llm_enabled": self.llm_enabled,
            "llm_available": self.llm_available,
            "market_data_provider": self.market_data_provider,
            "daily_llm_budget_usd": self.daily_llm_budget_usd,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
