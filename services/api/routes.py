"""API 로직 — 프레임워크에 의존하지 않는 순수 함수들.

★ 왜 이렇게 분리했는가
   서버 구현이 두 개(FastAPI / 표준 라이브러리)이기 때문입니다.
   로직을 여기 한 곳에 두면 두 서버의 응답이 달라질 수 없습니다.
   나중에 서버를 또 바꿔도 이 파일은 그대로 씁니다.

각 함수는 (status_code, dict) 를 돌려줍니다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.agent_registry import AgentStatus
from services.agent_runtime.engine import Engine

OK = 200
NOT_FOUND = 404
BAD_REQUEST = 400


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_ticker(sym: str) -> bool:
    """티커 검증 — 경로·명령 주입을 막는 첫 관문입니다."""
    s = (sym or "").strip().upper()
    return bool(s) and len(s) <= 12 and s.replace(".", "").replace("-", "").isalnum()


# ====================================================================== 시스템


def health(engine: Engine, llm_available: bool) -> tuple[int, dict]:
    return OK, {
        "status": "ok",
        "ts": _now(),
        "mock_mode": engine.mock_mode,
        # ★ MOCK / MIXED / REAL — mock_mode 하나로는 '일부만 실제' 를 표현할 수 없습니다.
        "data_mode": engine.data_mode(),
        "real_symbols": sorted(engine.real_symbols),
        "llm_connected": llm_available,
        "agents_total": len(engine.registry.all()),
        "agents_active": len(engine.registry.active()),
    }


def system_health(engine: Engine) -> tuple[int, dict]:
    return OK, engine.system_health()


# ====================================================================== 사무실


def office_layout(engine: Engine) -> tuple[int, dict]:
    return OK, {
        "grid": engine.layout.get("grid", {}),
        "rooms": engine.layout.get("rooms", []),
        "status_locations": engine.status_locations,
        "is_mock": engine.mock_mode,
    }


def office_agents(engine: Engine) -> tuple[int, dict]:
    return OK, {
        "agents": [
            st.summary()
            for st in engine.states.values()
            if st.profile.status == AgentStatus.ACTIVE
        ],
        "is_mock": engine.mock_mode,
    }


# ====================================================================== 에이전트


def list_agents(engine: Engine, status: str | None = None,
                department: str | None = None, sector: str | None = None,
                limit: int = 500) -> tuple[int, dict]:
    items = []
    for st in engine.states.values():
        p = st.profile
        if status and p.status.value != status.upper():
            continue
        if department and p.department != department:
            continue
        if sector and p.sector != sector:
            continue
        items.append(st.summary())
    return OK, {
        "counts": engine.registry.counts(),
        "departments": engine.registry.departments(),
        "sectors": engine.registry.sectors(),
        "agents": items[:limit],
        "note": (
            "정의된 에이전트는 많지만 ACTIVE 만 실제로 일합니다. "
            "REGISTERED 는 LLM 호출이 발생하지 않습니다."
        ),
    }


def agent_detail(engine: Engine, agent_id: str) -> tuple[int, dict]:
    st = engine.states.get(agent_id)
    if st is None:
        return NOT_FOUND, {"error": f"에이전트를 찾을 수 없습니다: {agent_id}"}
    detail = st.detail()
    detail["prediction_stats"] = engine.journal.agent_stats(agent_id)
    return OK, detail


# ====================================================================== 학습


def learning_overview(engine: Engine) -> tuple[int, dict]:
    rows = []
    for st in engine.states.values():
        if st.profile.status != AgentStatus.ACTIVE:
            continue
        rows.append({
            "agent_id": st.profile.id,
            "name": st.profile.name,
            "department": st.profile.department,
            "target_minutes": st.profile.learning_target_minutes,
            "effective_minutes": round(st.tracker.effective_seconds / 60, 1),
            "progress_pct": round(st.tracker.progress * 100, 1),
            "efficiency_pct": round(st.tracker.efficiency * 100, 1),
            "excluded_minutes": round(st.tracker.wasted_seconds / 60, 1),
            "documents_read": st.sources_read,
            "sources_rejected": st.sources_rejected,
            "knowledge_added": st.knowledge_added,
            "knowledge_rejected": st.knowledge_rejected,
            "chart_exercises": st.chart_exercises,
            "prediction_reviews": st.prediction_reviews,
            "chart_skill_score": st.model.chart_skill_score(),
            "daily_exam_score": st.last_exam_score,
            "source_exam_score": st.last_source_exam_score,
            "samples_seen": st.model.samples_seen,
            "accuracy_pct": round(st.model.accuracy * 100, 1),
            "calibration_error": round(st.model.calibration_error, 4),
        })
    rows.sort(key=lambda r: r["chart_skill_score"], reverse=True)
    return OK, {
        "learning_day": engine.day,
        "agents": rows,
        "knowledge": engine.knowledge.stats(),
        "time_scale": "ACCELERATED_SIMULATION",
        "note": (
            "유효 학습시간에서 idle·중복읽기·스팸·에러루프는 제외됩니다. "
            "시험은 학습에 쓰지 않은 문제(out-of-sample)로만 출제됩니다. "
            "표시되는 시간은 가속 시뮬레이션 값입니다."
        ),
        "is_mock": engine.mock_mode,
    }


def learning_detail(engine: Engine, agent_id: str) -> tuple[int, dict]:
    st = engine.states.get(agent_id)
    if st is None:
        return NOT_FOUND, {"error": f"에이전트를 찾을 수 없습니다: {agent_id}"}
    return OK, {
        "agent_id": agent_id,
        "name": st.profile.name,
        "time": st.tracker.to_dict(),
        "model": st.model.to_dict(),
        "recent_training": st.recent_training[-20:],
        "recent_mistakes": st.recent_mistakes[-20:],
        "is_mock": engine.mock_mode,
    }


# ====================================================================== 리서치


def create_research(engine: Engine, ticker: str,
                    sector: str | None = None) -> tuple[int, dict]:
    ticker = (ticker or "").strip().upper()
    if not ticker or len(ticker) > 12 or not ticker.replace(".", "").replace("-", "").isalnum():
        return BAD_REQUEST, {"error": "올바른 티커를 입력하세요 (예: NVDA)"}
    return OK, engine.create_research_job(ticker, sector)


def list_jobs(engine: Engine, limit: int = 20) -> tuple[int, dict]:
    jobs = sorted(engine.jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return OK, {"jobs": jobs[:limit], "is_mock": engine.mock_mode}


def get_job(engine: Engine, job_id: str) -> tuple[int, dict]:
    job = engine.jobs.get(job_id)
    if job is None:
        return NOT_FOUND, {"error": f"작업을 찾을 수 없습니다: {job_id}"}
    return OK, job


# ====================================================================== 백테스트


def run_backtest(engine: Engine, ticker: str, strategy: str = "sma_crossover",
                 commission_bps: float = 5.0,
                 slippage_bps: float = 5.0) -> tuple[int, dict]:
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return BAD_REQUEST, {"error": "티커를 입력하세요"}
    if strategy not in engine.STRATEGIES:
        return BAD_REQUEST, {
            "error": f"알 수 없는 전략: {strategy}",
            "available": engine.STRATEGIES,
        }
    for v, name in ((commission_bps, "commission_bps"), (slippage_bps, "slippage_bps")):
        if not 0 <= v <= 500:
            return BAD_REQUEST, {"error": f"{name} 는 0~500 사이여야 합니다"}
    try:
        payload = engine.run_backtest(ticker, strategy, commission_bps, slippage_bps)
    except ValueError as exc:
        return BAD_REQUEST, {"error": str(exc)}
    bt_id = f"bt{len(engine.backtests) + 1:04d}"
    payload["backtest_id"] = bt_id
    engine.backtests[bt_id] = payload
    return OK, payload


def list_backtests(engine: Engine, limit: int = 20) -> tuple[int, dict]:
    items = list(engine.backtests.values())[-limit:]
    return OK, {
        "backtests": [
            {k: v for k, v in b.items() if k != "equity_curve"} for b in items
        ],
        "strategies": engine.STRATEGIES,
        "is_mock": engine.mock_mode,
    }


def get_backtest(engine: Engine, bt_id: str) -> tuple[int, dict]:
    b = engine.backtests.get(bt_id)
    if b is None:
        return NOT_FOUND, {"error": f"백테스트를 찾을 수 없습니다: {bt_id}"}
    return OK, b


# ====================================================================== 패턴


def patterns(engine: Engine, horizon: int = 5, force: bool = False) -> tuple[int, dict]:
    if horizon not in (1, 5, 20):
        return BAD_REQUEST, {"error": "horizon 은 1, 5, 20 중 하나여야 합니다"}
    return OK, engine.mine_patterns(horizon=horizon, force=force)


# ====================================================================== 데이터


def data_providers(engine: Engine) -> tuple[int, dict]:
    """공급자 상태 (§49). 없는 걸 있다고 하지 않습니다."""
    now = _now()

    # 외부 수집기(Agent Reach 등) 상태. 설치되지 않아도 오류가 아닙니다.
    collectors = []
    try:
        from packages.data_connectors import AgentReachCollector

        collectors.append(
            AgentReachCollector(config_dir=engine.config_dir).health().to_dict()
        )
    except Exception as exc:  # 수집기 문제로 화면 전체가 죽으면 안 됩니다
        collectors.append({
            "id": "agent_reach", "name": "Agent Reach",
            "status": "ERROR", "detail": str(exc)[:200],
        })

    # ★ Phase 21/12 — 시세·공시 공급자의 '실제' 상태
    providers = [{
        "id": "mock_synthetic",
        "name": "합성 캔들 생성기 (MOCK)",
        "status": "CONNECTED",
        "kind": "OHLCV",
        "last_success": now,
        "record_count": sum(len(s) for s in engine._series_cache.values()),
        "requires_key": False,
        "cost": "무료",
        "note": "실제 시장 데이터가 아닙니다. 실데이터가 적재되면 종목별로 대체됩니다.",
    }]

    try:
        from packages.market_data import CsvFileProvider, StooqProvider, YFinanceProvider

        csv_p = CsvFileProvider(directory=getattr(engine, "market_data_dir",
                                                  "data/market"))
        h = csv_p.health()
        providers.append({
            "id": h["id"], "name": h["name"], "kind": "OHLCV",
            "status": h["status"], "requires_key": False, "cost": "무료",
            "record_count": len(h["symbols_found"]),
            "detail": (f"{h['directory']} 에서 {len(h['symbols_found'])}개 발견"
                       if h["symbols_found"] else
                       f"{h['directory']} 에 CSV 를 넣으면 자동 인식됩니다"),
            "verified": h["verified"], "note": h["terms_note"],
        })

        st = StooqProvider().health()
        providers.append({
            "id": st["id"], "name": st["name"], "kind": "OHLCV",
            "status": "AVAILABLE", "requires_key": False, "cost": "무료",
            "record_count": 0, "verified": st["verified"], "note": st["terms_note"],
            "detail": "API 키 불필요. 실제 연결은 사용자 PC 에서 처음 확인됩니다.",
        })

        yf = YFinanceProvider().health()
        providers.append({
            "id": yf["id"], "name": yf["name"], "kind": "OHLCV",
            "status": yf["status"], "requires_key": False, "cost": "무료",
            "record_count": 0, "verified": yf["verified"],
            "note": yf["terms_note"], "detail": yf["detail"],
        })
    except Exception as exc:                              # pragma: no cover
        providers.append({"id": "market_data", "name": "시세 공급자",
                          "status": "ERROR", "detail": str(exc)[:200]})

    # ★ 한국 데이터 (antking님이 선택한 두 곳)
    try:
        from packages.market_data import DataGoKrProvider

        h = DataGoKrProvider(
            service_key=getattr(engine, "data_go_kr_key", "")).health()
        providers.append({
            "id": h["id"], "name": h["name"], "kind": "OHLCV (KR)",
            "status": h["status"], "requires_key": True, "cost": "무료",
            "key_env": h["key_env"], "record_count": 0,
            "verified": h["verified"], "note": h["terms_note"],
            "detail": h["detail"],
        })
    except Exception as exc:                              # pragma: no cover
        providers.append({"id": "data_go_kr", "name": "공공데이터포털",
                          "status": "ERROR", "detail": str(exc)[:200]})

    try:
        from packages.dart import DartClient

        h = DartClient(api_key=getattr(engine, "dart_api_key", "")).health()
        providers.append({
            "id": h["id"], "name": h["name"], "kind": "FILINGS (KR)",
            "status": h["status"], "requires_key": True, "cost": "무료",
            "key_env": h["key_env"], "record_count": 0,
            "rate_limit": h["rate_limit"],
            "verified": h["verified"], "note": h["terms_note"],
            "detail": h["detail"],
        })
    except Exception as exc:                              # pragma: no cover
        providers.append({"id": "dart", "name": "DART",
                          "status": "ERROR", "detail": str(exc)[:200]})

    try:
        from packages.sec_edgar import EdgarClient

        email = getattr(engine, "sec_contact_email", "")
        h = EdgarClient(contact_email=email).health()
        providers.append({
            "id": h["id"], "name": h["name"], "kind": "FILINGS",
            "status": h["status"], "requires_key": False, "cost": "무료",
            "record_count": 0, "verified": h["verified"],
            "note": h["terms_note"], "detail": h["detail"],
            "rate_limit": h["rate_limit"],
        })
    except Exception as exc:                              # pragma: no cover
        providers.append({"id": "sec_edgar", "name": "SEC EDGAR",
                          "status": "ERROR", "detail": str(exc)[:200]})

    return OK, {
        "collectors": collectors,
        "collector_note": (
            "수집기는 '수집'만 합니다. 가져온 문서는 전부 Research Firewall 을 "
            "통과해야 하고, 등급은 우리 규칙으로 다시 정합니다. "
            "수집 경로가 신뢰도를 만들지 않습니다."
        ),
        "providers": providers,
        "market": engine.market_status(),
        "is_mock": engine.mock_mode,
    }


# ====================================================================== 시세


def markets(engine: Engine) -> tuple[int, dict]:
    """Markets 화면. 실제 데이터가 있을 때만 채워집니다."""
    return OK, engine.market_status()


def load_market(engine: Engine, symbols: str = "", provider: str = "csv_file",
                start: str = "", end: str = "") -> tuple[int, dict]:
    """시세를 적재합니다 (POST)."""
    allowed = {"csv_file", "stooq", "yfinance", "data_go_kr"}
    if provider not in allowed:
        return BAD_REQUEST, {"error": f"provider 는 {sorted(allowed)} 중 하나여야 합니다"}

    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    for s in syms:
        if not _valid_ticker(s):
            return BAD_REQUEST, {"error": f"종목 코드 형식이 아닙니다: {s}"}

    result = engine.load_market_data(
        symbols=syms or None, provider=provider,
        data_dir=getattr(engine, "market_data_dir", "data/market"),
        exchange=getattr(engine, "market_exchange", "XNYS"),
        start=start or None, end=end or None,
    )
    return (OK if result.get("ok") else BAD_REQUEST), result


def calendar_info(engine: Engine, exchange: str = "XNYS",
                  start: str = "", end: str = "") -> tuple[int, dict]:
    """거래일 캘린더 조회 (Phase 11)."""
    from datetime import date as _date

    from packages.market_calendar import CalendarError, get_calendar

    try:
        cal = get_calendar(exchange)
    except CalendarError as exc:
        return BAD_REQUEST, {"error": str(exc)}

    payload = {"coverage": cal.coverage()}
    if start and end:
        try:
            s = _date.fromisoformat(start)
            e = _date.fromisoformat(end)
            sessions = cal.sessions_between(s, e)
        except (ValueError, CalendarError) as exc:
            return BAD_REQUEST, {"error": str(exc)}
        payload["sessions"] = [d.isoformat() for d in sessions[:400]]
        payload["session_count"] = len(sessions)
        payload["early_closes"] = [
            {"date": d.isoformat(), "reason": cal.early_close_reason(d)}
            for d in sessions if cal.is_early_close(d)
        ][:50]
    return OK, payload


def sec_filings(engine: Engine, cik: str = "", forms: str = "",
                limit: int = 20) -> tuple[int, dict]:
    """SEC 공시 목록 (Phase 12)."""
    from packages.sec_edgar import EdgarClient

    if not cik.strip():
        return BAD_REQUEST, {"error": "cik 를 지정하세요 (예: 320193)"}

    client = EdgarClient(contact_email=getattr(engine, "sec_contact_email", ""))
    if not client.configured:
        return OK, {
            "ok": False,
            "error": (".env 의 SEC_CONTACT_EMAIL 이 비어 있습니다. "
                      "SEC 는 연락처 이메일을 요구하며, 없으면 차단됩니다. "
                      "비용은 들지 않습니다."),
            "filings": [],
        }
    form_tuple = tuple(f.strip().upper() for f in forms.split(",") if f.strip())
    result = client.fetch_filings(cik, forms=form_tuple, limit=max(1, min(limit, 100)))
    return OK, result


def dart_filings(engine: Engine, stock_code: str = "", begin: str = "",
                 end: str = "", limit: int = 30) -> tuple[int, dict]:
    """DART 한국 공시 목록."""
    from packages.dart import DartClient

    code = (stock_code or "").strip()
    if not code:
        return BAD_REQUEST, {"error": "stock_code 를 지정하세요 (예: 005930)"}
    if not _valid_ticker(code):
        return BAD_REQUEST, {"error": f"종목 코드 형식이 아닙니다: {code}"}

    client = DartClient(api_key=getattr(engine, "dart_api_key", ""))
    if not client.configured:
        return OK, {
            "ok": False,
            "error": (".env 의 DART_API_KEY 가 비어 있거나 형식이 맞지 않습니다. "
                      "opendart.fss.or.kr 에서 인증키를 발급받으세요 "
                      "(무료·40자리)."),
            "filings": [],
        }
    return OK, client.fetch_filings(
        stock_code=code, begin=begin, end=end, limit=max(1, min(limit, 100)))


def persistence(engine: Engine) -> tuple[int, dict]:
    """영속화 상태 (Phase 5b)."""
    return OK, engine.persistence_status()


def save_state(engine: Engine) -> tuple[int, dict]:
    """지금 상태를 즉시 저장 (POST)."""
    return OK, engine.save_state(reason="api")


# ====================================================================== 감사


def audit_events(engine: Engine, limit: int = 100) -> tuple[int, dict]:
    return OK, {
        "events": engine.bus.recent(limit),
        "total_emitted": engine.bus.total_emitted,
        "is_mock": engine.mock_mode,
    }


def audit_knowledge(engine: Engine, limit: int = 50) -> tuple[int, dict]:
    return OK, {
        "approved": [
            {
                "k_id": k.k_id, "statement": k.statement, "agent_id": k.agent_id,
                "confidence": k.confidence, "evidence_status": k.evidence_status,
                "independent_evidence_count": k.independent_evidence_count,
                "best_tier": k.best_tier, "approved_at": k.approved_at,
            }
            for k in list(engine.knowledge.approved.values())[-limit:]
        ],
        "rejected": [
            {
                "statement": r.statement, "agent_id": r.agent_id,
                "reasons": r.reasons, "times_seen": r.times_seen,
                "rejected_at": r.rejected_at,
            }
            for r in engine.knowledge.rejected[-limit:]
        ],
        "stats": engine.knowledge.stats(),
        "note": "기각된 지식도 보관합니다. 같은 거짓 정보가 다시 들어오면 대조합니다.",
    }


def audit_predictions(engine: Engine, limit: int = 50) -> tuple[int, dict]:
    preds = list(engine.journal.predictions.values())[-limit:]
    return OK, {
        "predictions": [
            {
                **p.to_dict(),
                "results": [r.to_dict() for r in engine.journal.results.get(p.pred_id, [])],
            }
            for p in preds
        ],
        "total": len(engine.journal.predictions),
    }


# ====================================================================== 스냅샷


def snapshot(engine: Engine) -> dict:
    """WebSocket 접속 직후 보내는 현재 상태 전체."""
    return {
        "type": "snapshot",
        "ts": _now(),
        "is_mock": engine.mock_mode,
        "data_mode": engine.data_mode(),
        "real_symbols": sorted(engine.real_symbols),
        "agents": [
            st.summary() for st in engine.states.values()
            if st.profile.status == AgentStatus.ACTIVE
        ],
        "system": engine.system_health(),
    }
