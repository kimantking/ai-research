"""FastAPI 서버 (기본 경로).

★ 로직은 여기 없습니다
   모든 응답은 services/api/routes.py 에서 나옵니다.
   standalone.py(표준 라이브러리 서버)와 같은 함수를 쓰므로
   두 서버의 응답이 달라질 수 없습니다.

실행:
    uvicorn services.api.main:app --host 127.0.0.1 --port 8010 --reload
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (
    BackgroundTasks,
    Body,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from packages.shared.config import get_settings
from packages.shared.logging import get_logger
from services.agent_runtime.engine import Engine

from . import routes

log = get_logger("api")
settings = get_settings()

engine: Engine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    db_path = None
    if settings.persistence == "sqlite":
        db_path = settings.project_root / settings.sqlite_path
    engine = Engine(config_dir=settings.config_dir, mock_mode=settings.mock_mode,
                    db_path=db_path,
                    autosave_every=settings.autosave_every_ticks)
    # 실데이터 설정을 엔진에 붙여둡니다 (라우트가 읽습니다)
    engine.market_data_dir = str(settings.project_root / settings.market_data_dir)
    engine.market_exchange = settings.market_exchange
    engine.sec_contact_email = settings.sec_contact_email
    engine.data_go_kr_key = settings.data_go_kr_key
    engine.dart_api_key = settings.dart_api_key
    log.info(
        "engine_ready",
        agents_total=len(engine.registry.all()),
        agents_active=len(engine.registry.active()),
        mock_mode=settings.mock_mode,
    )
    engine.start(interval=1.5)
    try:
        yield
    finally:
        await engine.stop()


app = FastAPI(
    title="AI Stock Research Office API",
    version="0.1.0",
    description=(
        "증거 우선 · 시점 무결성을 강제하는 AI 리서치 조직의 백엔드. "
        "실거래 기능은 없습니다."
    ),
    lifespan=lifespan,
)

# 로컬 개발용. 외부에 노출하지 않습니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.web_port}",
        f"http://127.0.0.1:{settings.web_port}",
        "http://localhost:3000",
        "http://localhost:3010",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


def _e() -> Engine:
    if engine is None:
        raise HTTPException(503, "엔진이 아직 시작되지 않았습니다")
    return engine


def _reply(result: tuple[int, dict]) -> dict:
    status, payload = result
    if status != 200:
        raise HTTPException(status, payload.get("error", "요청을 처리할 수 없습니다"))
    return payload


# ====================================================================== 화면


@app.get("/", include_in_schema=False)
def index():
    page = settings.static_dir / "office.html"
    if page.exists():
        return FileResponse(str(page))
    raise HTTPException(404, "office.html 을 찾을 수 없습니다")


# ====================================================================== 시스템


@app.get("/health", tags=["system"])
def health():
    return _reply(routes.health(_e(), settings.llm_available))


@app.get("/api/system/health", tags=["system"])
def system_health():
    return _reply(routes.system_health(_e()))


# ====================================================================== 사무실


@app.get("/api/office/layout", tags=["office"])
def office_layout():
    return _reply(routes.office_layout(_e()))


@app.get("/api/office/agents", tags=["office"])
def office_agents():
    return _reply(routes.office_agents(_e()))


# ====================================================================== 에이전트


@app.get("/api/agents", tags=["agents"])
def list_agents(status: str | None = None, department: str | None = None,
                sector: str | None = None, limit: int = 500):
    return _reply(routes.list_agents(_e(), status, department, sector, limit))


@app.get("/api/agents/{agent_id}", tags=["agents"])
def agent_detail(agent_id: str):
    return _reply(routes.agent_detail(_e(), agent_id))


# ====================================================================== 학습


@app.get("/api/learning", tags=["learning"])
def learning_overview():
    return _reply(routes.learning_overview(_e()))


@app.get("/api/learning/{agent_id}", tags=["learning"])
def learning_detail(agent_id: str):
    return _reply(routes.learning_detail(_e(), agent_id))


# ====================================================================== 리서치


class ResearchRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    sector: str | None = None


@app.post("/api/research", tags=["research"])
async def create_research(req: ResearchRequest, background: BackgroundTasks):
    payload = _reply(routes.create_research(_e(), req.ticker, req.sector))
    background.add_task(_run_job, payload["job_id"])
    return payload


async def _run_job(job_id: str):
    try:
        await _e().run_research(job_id)
    except Exception as exc:
        log.error("research_job_failed", job_id=job_id, error=str(exc))
        job = _e().jobs.get(job_id)
        if job:
            job["status"] = "FAILED"
            job["error"] = str(exc)


@app.get("/api/research", tags=["research"])
def list_jobs(limit: int = 20):
    return _reply(routes.list_jobs(_e(), limit))


@app.get("/api/research/{job_id}", tags=["research"])
def get_job(job_id: str):
    return _reply(routes.get_job(_e(), job_id))


# ====================================================================== 백테스트 / 패턴


class BacktestRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    strategy: str = "sma_crossover"
    commission_bps: float = 5.0
    slippage_bps: float = 5.0


@app.post("/api/backtest", tags=["backtest"])
def run_backtest(req: BacktestRequest):
    return _reply(routes.run_backtest(
        _e(), req.ticker, req.strategy, req.commission_bps, req.slippage_bps
    ))


@app.get("/api/backtest", tags=["backtest"])
def list_backtests(limit: int = 20):
    return _reply(routes.list_backtests(_e(), limit))


@app.get("/api/backtest/{bt_id}", tags=["backtest"])
def get_backtest(bt_id: str):
    return _reply(routes.get_backtest(_e(), bt_id))


@app.get("/api/patterns", tags=["patterns"])
def patterns(horizon: int = 5, force: bool = False):
    return _reply(routes.patterns(_e(), horizon, force))


# ====================================================================== 데이터 / 감사


@app.get("/api/data/providers", tags=["data"])
def data_providers():
    return _reply(routes.data_providers(_e()))


@app.get("/api/markets", tags=["data"])
def markets():
    return _reply(routes.markets(_e()))


@app.post("/api/data/load", tags=["data"])
def load_market(payload: dict = Body(default={})):
    return _reply(routes.load_market(
        _e(),
        symbols=str(payload.get("symbols", "")),
        provider=str(payload.get("provider", "csv_file")),
        start=str(payload.get("start", "")),
        end=str(payload.get("end", "")),
    ))


@app.get("/api/calendar", tags=["data"])
def calendar_info(exchange: str = "XNYS", start: str = "", end: str = ""):
    return _reply(routes.calendar_info(_e(), exchange, start, end))


@app.get("/api/sec/filings", tags=["data"])
def sec_filings(cik: str = "", forms: str = "", limit: int = 20):
    return _reply(routes.sec_filings(_e(), cik, forms, limit))


@app.get("/api/dart/filings", tags=["data"])
def dart_filings(stock_code: str = "", begin: str = "", end: str = "",
                 limit: int = 30):
    return _reply(routes.dart_filings(_e(), stock_code, begin, end, limit))


@app.get("/api/persistence", tags=["system"])
def persistence():
    return _reply(routes.persistence(_e()))


@app.post("/api/persistence/save", tags=["system"])
def save_state():
    return _reply(routes.save_state(_e()))


@app.get("/api/audit/events", tags=["audit"])
def audit_events(limit: int = 100):
    return _reply(routes.audit_events(_e(), limit))


@app.get("/api/audit/knowledge", tags=["audit"])
def audit_knowledge(limit: int = 50):
    return _reply(routes.audit_knowledge(_e(), limit))


@app.get("/api/audit/predictions", tags=["audit"])
def audit_predictions(limit: int = 50):
    return _reply(routes.audit_predictions(_e(), limit))


# ====================================================================== WebSocket


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    e = _e()
    loop = asyncio.get_running_loop()
    q = e.bus.subscribe_async(loop)
    try:
        # 접속 직후 현재 상태를 한 번에 보냅니다 (화면이 빈 채로 있지 않게)
        await ws.send_json(routes.snapshot(e))
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.send_json({
                    "type": "heartbeat",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "is_mock": e.mock_mode,
                })
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("ws_error", error=str(exc))
    finally:
        e.bus.unsubscribe_async(q)
