"""에이전트 런타임 엔진.

여기가 '실제로 일이 벌어지는 곳'입니다.
픽셀 사무실의 캐릭터가 움직이는 이유는 전부 이 파일에서 나옵니다.

에이전트가 실제로 하는 일 (LLM API 키 없이도 전부 동작합니다):
  - 차트 학습: 과거 구간을 잘라 미래를 가리고 예측 → 채점 → 가중치 갱신
  - 출처 검증: Research Firewall 로 스팸/중복/루머 판정
  - 지식 승인: 후보 → 검증 → 승인/기각 (기각도 보관)
  - 시험: 학습에 쓰지 않은 문제로 out-of-sample 채점
  - 오답 분석: 왜 틀렸는지 분류
  - 유효 학습시간 집계: idle·중복·스팸은 제외
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from packages.shared.yamlio import load_file

from packages.agent_registry import AgentProfile, AgentRegistry, AgentStatus, Role, Router
from packages.chart_skills.structure import market_structure
from packages.chart_skills.synth import generate_series, series_regime
from packages.evaluation.evidence_gate import EvidenceGate, EvidenceMissing
from packages.evaluation.journal import PredictionJournal
from packages.learning_engine.effective_time import EffectiveTimeTracker
from packages.learning_engine.exam import ChartExam, SourceExam
from packages.learning_engine.exercise import build_exercise, evaluate_exercise
from packages.learning_engine.knowledge import KnowledgeCandidate, KnowledgeStore
from packages.learning_engine.model import OnlineChartModel
from packages.shared.logging import get_logger
from packages.source_validation.firewall import ResearchFirewall
from packages.source_validation.lineage import LineageTracker, SourceRecord
from packages.source_validation.tiers import SourceTier

from .events import EventBus

log = get_logger("engine")

# 에이전트 상태 (§42)
STATUSES = [
    "SLEEPING", "IDLE", "WALKING", "SEARCHING", "RESEARCHING", "READING",
    "CHARTING", "LEARNING", "DEBATING", "VERIFYING", "BACKTESTING",
    "EVALUATING", "COMMITTEE", "CIO_REVIEW", "WAITING", "BLOCKED",
    "DONE", "ERROR",
]

# 데모용 종목 (MOCK). 실제 시세가 아닙니다.
DEMO_TICKERS = {
    "semiconductor": ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
    "biotech": ["MRNA", "VRTX", "REGN", "ALNY"],
    "energy": ["XOM", "CEG", "NEE", "OKLO"],
}


# ====================================================================== 에이전트 상태


@dataclass
class AgentRuntimeState:
    profile: AgentProfile
    status: str = "IDLE"
    location: str = ""
    target_location: str = ""
    current_task: str = "대기 중"
    ticker: str | None = None
    research_query: str = ""

    model: OnlineChartModel = None  # type: ignore[assignment]
    tracker: EffectiveTimeTracker = None  # type: ignore[assignment]
    firewall: ResearchFirewall = field(default_factory=ResearchFirewall)

    sources_read: int = 0
    sources_rejected: int = 0
    knowledge_added: int = 0
    knowledge_rejected: int = 0
    chart_exercises: int = 0
    prediction_reviews: int = 0

    last_exam_score: float | None = None
    last_source_exam_score: float | None = None
    sector_knowledge_score: float = 35.0

    recent_findings: list[str] = field(default_factory=list)
    recent_mistakes: list[dict] = field(default_factory=list)
    recent_training: list[dict] = field(default_factory=list)

    position: str | None = None       # BULL | BEAR | NEUTRAL
    confidence: float = 0.0

    # 내부 스케줄러
    _step: int = 0
    _program: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.model is None:
            self.model = OnlineChartModel(
                agent_id=self.profile.id, role_prior=self.profile.role_prior
            )
        if self.tracker is None:
            self.tracker = EffectiveTimeTracker(
                agent_id=self.profile.id,
                target_seconds=self.profile.learning_target_minutes * 60,
            )
        if not self.location:
            self.location = self.profile.home_location

    # ------------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "id": self.profile.id,
            "name": self.profile.name,
            "role": self.profile.role.value,
            "department": self.profile.department,
            "sector": self.profile.sector,
            "agent_status": self.profile.status.value,
            "status": self.status,
            "location": self.location,
            "current_task": self.current_task,
            "ticker": self.ticker,
            "confidence": round(self.confidence, 3),
            "position": self.position,
            "chart_skill_score": self.model.chart_skill_score(),
            "learning_progress_pct": round(self.tracker.progress * 100, 1),
        }

    def detail(self) -> dict:
        """캐릭터를 클릭하면 보이는 상세 정보 (§43)."""
        return {
            **self.summary(),
            "specialties": self.profile.specialties,
            "skills": self.profile.skills,
            "research_depth": self.profile.research_depth,
            "research_query": self.research_query,
            "model_policy": {
                "default": self.profile.model_policy.default.value,
                "cheap_tasks": self.profile.model_policy.cheap_tasks.value,
            },
            "learning": self.tracker.to_dict(),
            "counters": {
                "sources_read": self.sources_read,
                "sources_rejected": self.sources_rejected,
                "knowledge_added": self.knowledge_added,
                "knowledge_rejected": self.knowledge_rejected,
                "chart_exercises": self.chart_exercises,
                "prediction_reviews": self.prediction_reviews,
            },
            "scores": {
                "chart_skill": self.model.chart_skill_score(),
                "prediction_accuracy_pct": round(self.model.accuracy * 100, 1),
                "recent_accuracy_pct": round(self.model.recent_accuracy * 100, 1),
                "calibration_error": round(self.model.calibration_error, 4),
                "samples_seen": self.model.samples_seen,
                "daily_exam_score": self.last_exam_score,
                "source_verification_score": self.last_source_exam_score,
                "sector_knowledge": round(self.sector_knowledge_score, 1),
            },
            "model_weights": self.model.to_dict()["weights"],
            "recent_findings": self.recent_findings[-8:],
            "recent_mistakes": self.recent_mistakes[-8:],
            "recent_training": self.recent_training[-8:],
        }


# ====================================================================== 엔진


class Engine:
    def __init__(self, config_dir: Path, mock_mode: bool = True, seed: int = 7,
                 db_path: "str | Path | None" = None,
                 autosave_every: int = 200):
        self.config_dir = config_dir
        self.mock_mode = mock_mode
        self.bus = EventBus()
        self.registry = AgentRegistry.from_config(config_dir)
        self.router = Router(self.registry, max_agents=8)
        self.knowledge = KnowledgeStore()
        self.journal = PredictionJournal()
        self.rng = random.Random(seed)
        self.started_at = datetime.now(timezone.utc)
        self.tick_count = 0
        self.day = 0

        self.layout = self._load_layout()
        self.status_locations: dict[str, str] = self.layout.get("status_locations", {})

        self.states: dict[str, AgentRuntimeState] = {
            p.id: AgentRuntimeState(profile=p)
            for p in self.registry.all()
        }

        # 시세 캐시. 실제 데이터가 적재된 종목은 real_symbols 에 들어갑니다.
        self._series_cache: dict[str, Any] = {}
        self.real_symbols: set[str] = set()
        # PIT Store — 실데이터 적재 시 4개 시간축과 함께 들어갑니다
        from packages.pit_store.store import PITStore
        self.pit = PITStore()

        self.jobs: dict[str, dict] = {}
        self.backtests: dict[str, dict] = {}
        self._pattern_cache: dict[str, dict] = {}
        self._job_seq = 0
        self._task: asyncio.Task | None = None

        # 비용 장부 (§54). 지금은 LLM 을 호출하지 않으므로 0 입니다.
        self.cost_ledger: dict[str, float] = {}

        # ---------------------------------------------------------------
        # ★ Phase 5b — 영속화
        #   지금까지는 껐다 켜면 학습이 전부 사라졌습니다.
        #   SQLite 파일 하나로 그것을 이어붙입니다.
        #   저장소를 열지 못해도 시스템은 반드시 뜹니다(메모리 전용으로 계속).
        # ---------------------------------------------------------------
        self.store = None
        self.autosave_every = max(0, autosave_every)
        self.restore_report: dict = {"restored": False,
                                     "note": "영속화를 사용하지 않습니다."}
        self.restored_knowledge: list = []
        self.restored_knowledge_rejected: list = []
        self.last_save: dict = {}
        self._store_error: str = ""
        if db_path is not None:
            self._open_store(db_path)

        for st in self.states.values():
            st._program = self._make_program(st.profile)
            # ★ 시작 단계를 어긋나게 둡니다.
            #   전부 같은 단계에서 시작하면 16명이 한 방에 몰려 있다가
            #   다 같이 다른 방으로 우르르 옮겨갑니다. 사무실처럼 보이지 않고,
            #   부하도 한 순간에 몰립니다.
            if st._program:
                st._step = sum(ord(c) for c in st.profile.id) % len(st._program)

    # ------------------------------------------------------------------ 설정
    def _load_layout(self) -> dict:
        path = self.config_dir / "office_layout.yaml"
        if not path.exists():
            return {"grid": {"width": 64, "height": 38, "tile": 16}, "rooms": [],
                    "status_locations": {}}
        return load_file(path) or {}

    def _make_program(self, p: AgentProfile) -> list[str]:
        """에이전트별 하루 루틴. 역할에 따라 다릅니다."""
        if p.role in (Role.SOURCE_VERIFICATION, Role.DATA_QUALITY):
            return ["verify_sources", "verify_sources", "study_document",
                    "source_exam", "idle"]
        if p.role in (Role.CIO, Role.INVESTMENT_COMMITTEE, Role.CHIEF_LEARNING_OFFICER):
            # 임원도 논다고 시간이 가지 않습니다. 조직 전체의 예측을 복기하고
            # 자료를 읽습니다.
            return ["review_predictions", "study_document", "study_document",
                    "review_predictions", "source_exam", "idle"]
        if p.role == Role.EVIDENCE_JUDGE:
            return ["study_document", "review_predictions", "source_exam",
                    "chart_study", "idle"]
        if p.role in (Role.TECHNICAL_MASTER, Role.TECHNICAL_BULL, Role.TECHNICAL_BEAR):
            return ["chart_study", "chart_study", "chart_study", "chart_exam", "idle"]
        # 섹터 팀 — 역할마다 루틴을 조금씩 다르게 해서 사무실이 한쪽으로 쏠리지 않게 합니다
        if p.role == Role.SECTOR_LEAD:
            return ["study_document", "chart_study", "review_predictions",
                    "study_document", "chart_exam", "source_exam", "idle"]
        if p.role == Role.BEAR_RESEARCHER:
            return ["study_document", "study_document", "chart_study",
                    "chart_exam", "review_predictions", "idle", "chart_study"]
        return ["chart_study", "study_document", "chart_study",
                "review_predictions", "chart_exam", "idle"]

    # ------------------------------------------------------------------ 시세
    def series_for(self, ticker: str, length: int = 420):
        """이 종목의 캔들.

        ★ 실제 데이터가 있으면 그것을 씁니다. 없으면 합성입니다.
          어느 쪽인지는 `self.real_symbols` 로 언제든 확인할 수 있고,
          화면의 MOCK 배지도 그것을 따릅니다. 섞어 쓰지 않습니다.
        """
        if ticker not in self._series_cache:
            real = self._real_series(ticker, length)
            if real is not None:
                self._series_cache[ticker] = real
                self.real_symbols.add(ticker)
            else:
                seed = abs(hash(ticker)) % 100_000 + 1000
                self._series_cache[ticker] = generate_series(seed=seed, length=length)
        return self._series_cache[ticker]

    def _real_series(self, ticker: str, length: int):
        """저장소에 적재된 실제 캔들이 있으면 꺼냅니다."""
        if self.store is None:
            return None
        try:
            rows = self.store.get_bars(ticker.upper(), limit=max(length, 100))
        except Exception:
            return None
        if len(rows) < 120:      # 학습·백테스트에 쓸 만큼은 있어야 합니다
            return None
        from packages.chart_skills.series import Candle, OHLCV
        return OHLCV([
            Candle(ts=int(r["ts"]), open=float(r["o"]), high=float(r["h"]),
                   low=float(r["l"]), close=float(r["c"]), volume=float(r["v"]))
            for r in rows[-length:]
        ])

    # ------------------------------------------------------------------ 실데이터
    def load_market_data(self, symbols: "list[str] | None" = None,
                         provider: str = "csv_file",
                         data_dir: str = "data/market",
                         exchange: str = "XNYS",
                         start: str | None = None,
                         end: str | None = None) -> dict:
        """공급자에서 실제 캔들을 받아 저장소와 PIT Store 에 적재합니다.

        어떤 종목이 실제 데이터이고 어떤 종목이 합성인지 결과에 그대로 남깁니다.
        """
        from packages.market_data import (
            CsvFileProvider, DataGoKrProvider, StooqProvider, YFinanceProvider,
            ingest_bars,
        )

        if self.store is None:
            return {"ok": False,
                    "error": "영속화가 꺼져 있어 시세를 저장할 수 없습니다 "
                             "(.env 의 PERSISTENCE=sqlite)"}

        if provider == "csv_file":
            prov = CsvFileProvider(directory=data_dir, exchange=exchange)
            symbols = symbols or prov.available()
        elif provider == "stooq":
            prov = StooqProvider(exchange=exchange)
        elif provider == "yfinance":
            prov = YFinanceProvider(exchange=exchange)
        elif provider == "data_go_kr":
            prov = DataGoKrProvider(
                service_key=getattr(self, "data_go_kr_key", ""),
                exchange=exchange or "XKRX",
            )
            if not prov.configured:
                return {"ok": False, "provider": provider, "loaded": [], "failed": [],
                        "error": (".env 의 DATA_GO_KR_KEY 가 비어 있습니다. "
                                  "data.go.kr 에서 '금융위원회_주식시세정보' 활용신청 후 "
                                  "인증키를 넣어주세요 (무료).")}
        else:
            return {"ok": False, "error": f"모르는 공급자입니다: {provider}"}

        if not symbols:
            return {"ok": False, "provider": provider, "loaded": [], "failed": [],
                    "error": (f"가져올 종목이 없습니다. "
                              f"{data_dir}/ 에 CSV 를 넣거나 종목을 지정하세요.")}

        loaded, failed = [], []
        for sym in symbols[:50]:
            res = prov.fetch(sym, start=start, end=end)
            if not res.ok or res.bars is None:
                failed.append({"symbol": sym, "error": res.error})
                continue
            if res.quality and not res.quality.usable:
                failed.append({"symbol": sym,
                               "error": "품질 검사 불합격: "
                                        + "; ".join(res.quality.problems)})
                continue
            rep = ingest_bars(res.bars, store=self.store,
                              pit_store=getattr(self, "pit", None),
                              exchange=exchange, source_id=prov.id)
            self._series_cache.pop(sym.upper(), None)
            self.real_symbols.add(sym.upper())
            loaded.append({**rep,
                           "quality": res.quality.to_dict() if res.quality else None})

        if loaded:
            # ★ mock_mode 를 끄지 않습니다.
            #   2종목이 실제라고 해서 나머지 합성 종목이 실제가 되지 않습니다.
            #   화면 배지는 data_mode(MOCK / MIXED / REAL)로 정확히 구분합니다.
            self.bus.emit("data.loaded", is_mock=self.data_mode() != "REAL",
                          detail=f"{provider}: 실제 캔들 {len(loaded)}종목 적재")
        return {
            "ok": bool(loaded),
            "provider": provider,
            "loaded": loaded,
            "failed": failed,
            "real_symbols": sorted(self.real_symbols),
            "note": ("적재된 종목만 실제 데이터입니다. 나머지는 여전히 합성입니다. "
                     "화면의 MOCK 배지는 종목 단위로 판단하십시오."),
        }

    def data_mode(self) -> str:
        """지금 쓰는 데이터가 어떤 상태인가.

            MOCK  — 전부 합성
            MIXED — 일부만 실제 (★ 가장 오해하기 쉬운 상태라 따로 둡니다)
            REAL  — 사용 중인 종목이 전부 실제

        "실데이터를 조금 넣었으니 이제 LIVE" 라고 말하면 거짓말이 됩니다.
        """
        used = set(self._series_cache)
        if not self.real_symbols:
            return "MOCK"
        if used and used <= self.real_symbols:
            return "REAL"
        return "MIXED"

    def market_status(self) -> dict:
        """Markets 화면이 쓰는 요약."""
        symbols = []
        if self.store is not None:
            try:
                for sym in self.store.symbols():
                    rows = self.store.get_bars(sym, limit=5000)
                    if not rows:
                        continue
                    last, first = rows[-1], rows[0]
                    prev = rows[-2] if len(rows) > 1 else last
                    change = ((last["c"] - prev["c"]) / prev["c"] * 100
                              if prev["c"] else 0.0)
                    symbols.append({
                        "symbol": sym,
                        "bars": len(rows),
                        "first_ts": first["ts"],
                        "last_ts": last["ts"],
                        "last_close": round(last["c"], 4),
                        "change_pct": round(change, 2),
                        "source": last.get("source", ""),
                        "adjusted": bool(last.get("adjusted", 0)),
                        "is_real": True,
                    })
            except Exception as exc:                      # pragma: no cover
                return {"error": str(exc), "symbols": []}

        return {
            "symbols": symbols,
            "data_mode": self.data_mode(),
            "real_symbol_count": len(symbols),
            "mock_symbols": sorted(
                s for s in self._series_cache if s not in self.real_symbols),
            "is_mock": not symbols,
            "note": (
                "여기에 보이는 종목만 실제 시장 데이터입니다."
                if symbols else
                "실제 시장 데이터가 아직 없습니다. "
                "data/market/ 에 CSV 를 넣고 .\\fetch-data.ps1 을 실행하거나, "
                "Data 화면에서 공급자를 확인하세요."
            ),
        }

    def _pick_ticker(self, st: AgentRuntimeState) -> str:
        pool = DEMO_TICKERS.get(st.profile.sector or "", None)
        if not pool:
            pool = [t for v in DEMO_TICKERS.values() for t in v]
        return self.rng.choice(pool)

    # ------------------------------------------------------------------ 이동
    def _location_for(self, st: AgentRuntimeState, status: str) -> str:
        loc = self.status_locations.get(status, "home")
        return st.profile.home_location if loc == "home" else loc

    def _set_status(self, st: AgentRuntimeState, status: str, task: str,
                    **extra) -> None:
        target = self._location_for(st, status)
        moved = target != st.location
        if moved:
            st.status = "WALKING"
            st.target_location = target
            self.bus.emit(
                "agent.status_changed", is_mock=self.mock_mode,
                agent_id=st.profile.id, status="WALKING",
                location=st.location, target_location=target,
                detail=f"{target} 로 이동", current_task=task,
            )
            st.location = target
        st.status = status
        st.current_task = task
        self.bus.emit(
            "agent.status_changed", is_mock=self.mock_mode,
            agent_id=st.profile.id, status=status, location=st.location,
            target_location=st.location, detail=task, current_task=task,
            ticker=st.ticker, **extra,
        )

    # ================================================================== 학습 단계

    def _do_chart_study(self, st: AgentRuntimeState) -> None:
        """차트 학습 — 진짜 계산이 돌아갑니다."""
        ticker = self._pick_ticker(st)
        st.ticker = ticker
        series = self.series_for(ticker)
        cut = self.rng.randint(80, len(series) - 25)
        horizon = self.rng.choice([1, 5, 20])
        ex = build_exercise(series, cut, ticker, horizon=horizon)
        if ex is None:
            st.tracker.record("error_retry", 5, "문제 생성 실패")
            return

        self._set_status(st, "CHARTING", f"{ticker} {horizon}일 전망 학습")

        result = evaluate_exercise(st.model, ex, learn=True)
        if result.get("skipped"):
            st.tracker.record("invalid_data", 4, result.get("reason", ""))
            return

        st.chart_exercises += 1
        # 문제 하나당 유효 학습 40~90초로 계산
        st.tracker.record("chart_exercise", self.rng.uniform(40, 90),
                          f"{ticker} {horizon}D")

        st.confidence = result["confidence"]
        st.position = "BULL" if result["predicted"] == "UP" else "BEAR"

        # ★ 판단은 전부 기록합니다 (§33). 차트 학습 예측도 판단입니다.
        #   기록하지 않으면 나중에 "이 에이전트가 얼마나 맞췄나"를 물을 수 없습니다.
        structure = market_structure(ex.past)
        structure["as_of_index"] = cut
        pred = self.journal.record(
            agent_id=st.profile.id,
            ticker=ticker,
            price_at_prediction=ex.past.closes[-1],
            direction=result["predicted"],
            confidence=result["confidence"],
            time_horizon_days=horizon,
            thesis=f"차트 학습 예측 ({horizon}일)",
            chart_state=structure,
            market_regime=series_regime(ex.past),
            evidence_ids=[f"CHART:{ticker}:{cut}"],
            is_mock=self.mock_mode,
        )
        # 학습 문제는 미래가 이미 정해져 있으므로 즉시 채점합니다.
        future = series[cut + 1 : cut + 1 + horizon]
        self.journal.evaluate(
            pred.pred_id, horizon, future.closes, future.highs, future.lows
        )

        training = {
            "type": "chart_exercise",
            "ticker": ticker,
            "horizon": horizon,
            "predicted": result["predicted"],
            "actual": result["actual"],
            "correct": result["correct"],
            "actual_return_pct": result["actual_return_pct"],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        st.recent_training.append(training)
        st.recent_training = st.recent_training[-20:]

        if not result["correct"]:
            cat = result.get("failure_category", "UNKNOWN")
            st.recent_mistakes.append({
                "ticker": ticker, "horizon": horizon, "category": cat,
                "predicted": result["predicted"], "actual": result["actual"],
                "ts": training["ts"],
            })
            st.recent_mistakes = st.recent_mistakes[-20:]
            st.tracker.record("failure_analysis", self.rng.uniform(20, 45), cat)
            self.bus.emit("agent.mistake", is_mock=self.mock_mode,
                          agent_id=st.profile.id, ticker=ticker,
                          category=cat, detail=f"{ticker} {horizon}D 예측 실패: {cat}")
        else:
            st.recent_findings.append(
                f"{ticker} {horizon}일 전망 적중 ({result['actual_return_pct']:+.2f}%)"
            )
            st.recent_findings = st.recent_findings[-20:]

        self.bus.emit(
            "agent.learned", is_mock=self.mock_mode,
            agent_id=st.profile.id, ticker=ticker,
            correct=result["correct"],
            chart_skill_score=st.model.chart_skill_score(),
            samples_seen=st.model.samples_seen,
            detail=f"{ticker} {horizon}D — {'적중' if result['correct'] else '오답'}",
        )

    def _do_study_document(self, st: AgentRuntimeState) -> None:
        """자료 정독 + 지식 후보 제출."""
        self._set_status(st, "READING", "자료 정독 및 검증")

        doc = self._synth_document(st)
        verdict = st.firewall.check(
            source_id=doc["source_id"], url=doc["url"], title=doc["title"],
            body=doc["body"], published=doc["published"],
            claims_recent=doc["claims_recent"],
        )
        st.sources_read += 1

        if not verdict.passed:
            st.sources_rejected += 1
            reason = verdict.reasons[0] if verdict.reasons else "필터링됨"
            # ★ 스팸/중복은 학습시간에서 제외됩니다
            activity = "duplicate_read" if verdict.is_duplicate_of else "spam_filtered"
            st.tracker.record(activity, self.rng.uniform(10, 25), reason)
            self.bus.emit("agent.source_rejected", is_mock=self.mock_mode,
                          agent_id=st.profile.id, url=doc["url"],
                          reason=reason, tier=verdict.tier.value,
                          detail=f"출처 거부: {reason}")
            return

        st.tracker.record("document_study", self.rng.uniform(60, 150),
                          doc["title"], content_hash=verdict.content_hash)

        # 지식 후보 제출
        sources = [
            SourceRecord(
                source_id=doc["source_id"], url=doc["url"], domain=doc["domain"],
                tier=verdict.tier, title=doc["title"], confidence=verdict.confidence,
            )
        ]
        # 독립 근거가 하나 더 있는 경우를 재현 (확정 사실이 되려면 2개 필요)
        if doc["has_second_source"]:
            sources.append(
                SourceRecord(
                    source_id=doc["source_id"] + "-b", url="https://www.sec.gov/x",
                    domain="sec.gov", tier=SourceTier.S, title="Filing",
                    confidence=1.0,
                )
            )

        cand = KnowledgeCandidate(
            statement=doc["claim"], agent_id=st.profile.id, sources=sources
        )
        outcome, info = self.knowledge.submit(cand)
        st.tracker.record("knowledge_verify", self.rng.uniform(20, 50), outcome.value)

        if outcome.value == "APPROVED":
            st.knowledge_added += 1
            st.sector_knowledge_score = min(100.0, st.sector_knowledge_score + 0.6)
            st.recent_findings.append(f"지식 승인: {doc['claim'][:60]}")
            st.recent_findings = st.recent_findings[-20:]
        elif outcome.value == "REJECTED":
            st.knowledge_rejected += 1
        # NEEDS_MORE_RESEARCH 는 버리지 않고 다음 라운드로 넘깁니다

        self.bus.emit("agent.knowledge", is_mock=self.mock_mode,
                      agent_id=st.profile.id, outcome=outcome.value,
                      statement=doc["claim"][:120],
                      detail=f"지식 검증: {outcome.value}")

    def _do_verify_sources(self, st: AgentRuntimeState) -> None:
        self._set_status(st, "VERIFYING", "출처 검증 (Research Firewall)")
        for _ in range(3):
            self._do_study_document_quiet(st)

    def _do_study_document_quiet(self, st: AgentRuntimeState) -> None:
        doc = self._synth_document(st)
        v = st.firewall.check(doc["source_id"], doc["url"], doc["title"],
                              doc["body"], published=doc["published"],
                              claims_recent=doc["claims_recent"])
        st.sources_read += 1
        if v.passed:
            st.tracker.record("document_study", self.rng.uniform(30, 60),
                              doc["title"], content_hash=v.content_hash)
        else:
            st.sources_rejected += 1
            st.tracker.record(
                "duplicate_read" if v.is_duplicate_of else "spam_filtered",
                self.rng.uniform(8, 18), v.reasons[0] if v.reasons else "",
            )

    def _do_review_predictions(self, st: AgentRuntimeState) -> None:
        """과거 예측 복기 (§33~35)."""
        self._set_status(st, "EVALUATING", "과거 예측 복기")
        # 임원과 Evidence Judge 는 조직 전체의 예측을 복기합니다.
        # 자기가 낸 예측만 보면 조직의 실수를 배울 수 없습니다.
        org_wide = st.profile.role in (
            Role.CIO, Role.INVESTMENT_COMMITTEE,
            Role.CHIEF_LEARNING_OFFICER, Role.EVIDENCE_JUDGE,
        )
        mine = [
            p for p in self.journal.predictions.values()
            if org_wide or p.agent_id == st.profile.id
        ]
        if not mine:
            st.tracker.record("waiting", 10, "복기할 예측 없음")
            return
        pred = self.rng.choice(mine[-20:])
        series = self.series_for(pred.ticker)
        # ★ 예측이 내려진 그 시점(as_of_index) 바로 다음 봉부터 채점합니다.
        #   아무 구간이나 가져다 채점하면 평가 자체가 거짓말이 됩니다.
        as_of = (pred.chart_state or {}).get("as_of_index")
        if as_of is None:
            st.tracker.record("invalid_data", 8, "예측에 as_of 시점이 없음")
            return
        start = as_of + 1
        end = start + pred.time_horizon_days
        if end > len(series):
            st.tracker.record("waiting", 10, "평가 시점 미도래")
            return
        after = series[start:end]
        res = self.journal.evaluate(
            pred.pred_id, pred.time_horizon_days,
            after.closes, after.highs, after.lows,
        )
        st.prediction_reviews += 1
        st.tracker.record("prediction_review", self.rng.uniform(30, 70), pred.ticker)
        if res and not res.direction_correct:
            st.recent_mistakes.append({
                "ticker": pred.ticker, "horizon": pred.time_horizon_days,
                "category": res.failure_category, "predicted": pred.direction,
                "actual": "UP" if res.actual_return > 0 else "DOWN",
                "ts": res.evaluated_at,
            })
            st.recent_mistakes = st.recent_mistakes[-20:]
        self.bus.emit("agent.prediction_reviewed", is_mock=self.mock_mode,
                      agent_id=st.profile.id, ticker=pred.ticker,
                      correct=bool(res and res.direction_correct),
                      detail=f"{pred.ticker} 예측 복기 완료")

    def _do_chart_exam(self, st: AgentRuntimeState) -> None:
        """일일 시험 — 학습에 쓰지 않은 문제로만 (§40)."""
        # 시험은 자기 자리에서 봅니다 (LEARNING → home)
        self._set_status(st, "LEARNING", "일일 차트 시험 (out-of-sample)")
        exam = ChartExam(questions=12, horizon=5)
        result = exam.take(st.model, exam_day=self.day)
        st.last_exam_score = result.score
        st.tracker.record("exam", self.rng.uniform(90, 150), "chart_daily")
        st.recent_training.append({
            "type": "exam", "exam": "chart_daily", "score": result.score,
            "accuracy_pct": round(result.accuracy * 100, 1),
            "ts": result.taken_at,
        })
        st.recent_training = st.recent_training[-20:]
        self.bus.emit("agent.exam", is_mock=self.mock_mode,
                      agent_id=st.profile.id, exam_type="chart_daily",
                      score=result.score, accuracy_pct=round(result.accuracy * 100, 1),
                      detail=f"일일 차트 시험 {result.score}점 "
                             f"({result.correct}/{result.total})")

    def _do_source_exam(self, st: AgentRuntimeState) -> None:
        self._set_status(st, "LEARNING", "출처 검증 시험")
        result = SourceExam().take(st.profile.id, exam_day=self.day)
        st.last_source_exam_score = result.score
        st.tracker.record("exam", self.rng.uniform(60, 100), "source_verification")
        st.recent_training.append({
            "type": "exam", "exam": "source_verification", "score": result.score,
            "accuracy_pct": round(result.accuracy * 100, 1), "ts": result.taken_at,
        })
        st.recent_training = st.recent_training[-20:]
        self.bus.emit("agent.exam", is_mock=self.mock_mode,
                      agent_id=st.profile.id, exam_type="source_verification",
                      score=result.score,
                      accuracy_pct=round(result.accuracy * 100, 1),
                      detail=f"출처 검증 시험 {result.score}점")

    def _do_idle(self, st: AgentRuntimeState) -> None:
        self._set_status(st, "IDLE", "대기 중")
        # ★ idle 은 유효 학습시간에 들어가지 않습니다
        st.tracker.record("idle", self.rng.uniform(20, 60), "대기")

    # ------------------------------------------------------------------ 합성 문서
    _SPAM_TEMPLATES = [
        ("충격! {t} 폭등 임박, 지금 사야 합니다",
         "충격! {t} 이 다음 주 폭등 임박! 세력이 들어왔다는 소문! "
         "작전주 정보! 수익률 500% 가능! 지금 사야 합니다! 놓치면 후회! "
         "이 기사는 보도자료를 기반으로 작성되었습니다."),
    ]
    _LEGIT_TEMPLATES = [
        ("{t} quarterly results filed",
         "According to the 10-Q filed with the SEC, {t} reported revenue of "
         "$4.2 billion for the quarter with a gross margin of 61.3%. "
         "The filing discloses segment detail and capital expenditure of "
         "$820 million. Management commentary in the same filing referenced "
         "existing supply agreements."),
        ("{t} discloses new agreement",
         "Per the 8-K filed with the SEC, {t} entered into a supply agreement. "
         "The filing states the initial term is three years. Reuters reported "
         "the announcement citing the same filing. According to the document, "
         "no financial terms were disclosed."),
    ]
    _RUMOR_TEMPLATES = [
        ("{t} 대형 계약설",
         "익명의 소식통에 따르면 {t} 가 대형 계약을 앞두고 있다고 한다. "
         "업계 관계자는 익명을 전제로 규모가 상당하다고 전했다. "
         "회사 측은 공식 입장을 내지 않았다."),
    ]

    def _synth_document(self, st: AgentRuntimeState) -> dict:
        """MOCK 문서 생성. 실제 뉴스가 아닙니다.

        Phase 13 에서 실제 크롤러로 바뀌지만, Research Firewall 코드는 그대로입니다.
        """
        ticker = st.ticker or self._pick_ticker(st)
        roll = self.rng.random()
        if roll < 0.22:
            tmpl = self.rng.choice(self._SPAM_TEMPLATES)
            domain, tier_hint = "pumpalert.example.com", "D"
            claim = f"{ticker} 가 곧 폭등한다"
            second = False
        elif roll < 0.36:
            tmpl = self.rng.choice(self._RUMOR_TEMPLATES)
            domain, tier_hint = "reddit.com", "E"
            claim = f"{ticker} 가 대형 계약을 앞두고 있다는 소문"
            second = False
        else:
            tmpl = self.rng.choice(self._LEGIT_TEMPLATES)
            domain = self.rng.choice(["sec.gov", "reuters.com", "bloomberg.com"])
            tier_hint = "S" if domain == "sec.gov" else "A"
            claim = f"{ticker} 의 최근 분기 매출이 공시를 통해 확인되었다"
            second = self.rng.random() < 0.6

        title, body = tmpl[0].format(t=ticker), tmpl[1].format(t=ticker)
        # 20% 확률로 '이미 본 문서'를 다시 제시 → 중복 탐지 테스트
        sid = f"src-{self.rng.randint(1, 40)}" if self.rng.random() < 0.2 \
            else f"src-{self.rng.randint(1000, 999999)}"

        age_days = self.rng.choice([0, 1, 2, 5, 30, 900])
        return {
            "source_id": sid,
            "url": f"https://{domain}/article/{sid}",
            "domain": domain,
            "title": title,
            "body": body,
            "claim": claim,
            "published": datetime.now(timezone.utc) - timedelta(days=age_days),
            "claims_recent": age_days > 300 and self.rng.random() < 0.5,
            "has_second_source": second,
            "tier_hint": tier_hint,
        }

    # ================================================================== 틱 루프

    STEP_HANDLERS = {
        "chart_study": "_do_chart_study",
        "study_document": "_do_study_document",
        "verify_sources": "_do_verify_sources",
        "review_predictions": "_do_review_predictions",
        "chart_exam": "_do_chart_exam",
        "source_exam": "_do_source_exam",
        "idle": "_do_idle",
    }

    def tick(self) -> None:
        """한 틱: 활성 에이전트가 각자 다음 단계를 하나씩 수행합니다."""
        self.tick_count += 1
        for st in self.states.values():
            if st.profile.status != AgentStatus.ACTIVE:
                continue
            if not st._program:
                continue
            step = st._program[st._step % len(st._program)]
            st._step += 1
            handler = getattr(self, self.STEP_HANDLERS[step])
            try:
                handler(st)
            except Exception as exc:  # 한 명이 넘어져도 사무실 전체가 멈추면 안 됩니다
                st.status = "BLOCKED"
                st.current_task = f"오류: {exc}"
                st.tracker.record("error_retry", 15, str(exc))
                log.error("agent_step_failed", agent_id=st.profile.id,
                          step=step, error=str(exc))
                self.bus.emit("agent.blocked", is_mock=self.mock_mode,
                              agent_id=st.profile.id, detail=f"오류: {exc}")

        # 하루가 지나면 학습시간 장부를 리셋합니다
        if self.tick_count % 240 == 0:
            self.day += 1
            for st in self.states.values():
                st.tracker.reset_day()
            self.bus.emit("system.new_day", is_mock=self.mock_mode, day=self.day,
                          detail=f"학습 {self.day}일차 시작")
            # 하루가 끝나면 반드시 저장합니다 (여기서 잃으면 하루치가 날아갑니다)
            self.save_state(reason="new_day")

        # 주기적 자동 저장
        if (self.store is not None and self.autosave_every
                and self.tick_count % self.autosave_every == 0):
            self.save_state(reason="autosave")

    # ================================================================== 영속화
    def _open_store(self, db_path) -> None:
        """저장소를 열고 이전 상태를 복구합니다.

        ★ 실패해도 절대 예외를 밖으로 던지지 않습니다.
          "DB 때문에 프로그램이 안 켜진다" 는 최악의 결과입니다.
        """
        try:
            from packages.persistence import SqliteStore, restore_engine
            self.store = SqliteStore(db_path)
            self.restore_report = restore_engine(self, self.store)
            if self.restored_knowledge or self.restored_knowledge_rejected:
                self._reload_knowledge(self.restored_knowledge)
            # ★ 저장소에 실제 캔들이 남아 있으면 재시작 직후부터 인식해야 합니다.
            #   이걸 빠뜨리면 실데이터가 DB 에 있는데도 화면이 MOCK 으로 뜹니다.
            try:
                self.real_symbols.update(self.store.symbols())
                self.restore_report["real_symbols"] = sorted(self.real_symbols)
            except Exception:
                pass
            log.info("persistence_ready", path=str(db_path),
                     restored=self.restore_report.get("restored"))
        except Exception as exc:
            self.store = None
            self._store_error = str(exc)
            self.restore_report = {
                "restored": False,
                "errors": [str(exc)],
                "note": ("저장소를 열지 못해 메모리 전용으로 실행합니다. "
                         "학습 결과는 종료 시 사라집니다."),
            }
            log.error("persistence_unavailable", error=str(exc))

    def _reload_knowledge(self, rows: list) -> None:
        """승인·기각된 지식을 되돌립니다.

        기각 이력이 특히 중요합니다. 그것을 잃으면 어제 걸러낸 루머를
        오늘 다시 검증하게 되고, "이전에 기각됨" 판정이 동작하지 않습니다.
        """
        from packages.learning_engine.knowledge import (
            ApprovedKnowledge, RejectedKnowledge,
        )

        ap_fields = set(ApprovedKnowledge.__dataclass_fields__)
        rj_fields = set(RejectedKnowledge.__dataclass_fields__)

        restored = 0
        for row in rows:
            if not isinstance(row, dict) or not row.get("k_id"):
                continue
            try:
                item = ApprovedKnowledge(
                    **{k: v for k, v in row.items() if k in ap_fields})
            except (TypeError, ValueError):
                continue
            self.knowledge.approved[item.k_id] = item
            self.knowledge._approved_sims.append((item.simhash, item.k_id))
            restored += 1

        rejected_rows = getattr(self, "restored_knowledge_rejected", []) or []
        rejected = 0
        for row in rejected_rows:
            if not isinstance(row, dict):
                continue
            try:
                self.knowledge.rejected.append(
                    RejectedKnowledge(
                        **{k: v for k, v in row.items() if k in rj_fields}))
                rejected += 1
            except (TypeError, ValueError):
                continue

        self.restore_report["knowledge_restored"] = restored
        self.restore_report["knowledge_rejected_restored"] = rejected

    def save_state(self, reason: str = "manual") -> dict:
        """지금까지 배운 것을 저장합니다. 실패해도 시스템은 계속 돕니다."""
        if self.store is None:
            self.last_save = {"saved": False, "reason": "저장소 없음"}
            return self.last_save
        try:
            from packages.persistence import snapshot_engine
            snap = snapshot_engine(self, self.store)
            self.last_save = {"saved": True, "trigger": reason, **snap.to_dict()}
            self.bus.emit("system.state_saved", is_mock=self.mock_mode,
                          detail=f"학습 상태 저장 ({snap.agents_saved}명 / "
                                 f"예측 {snap.predictions_saved}건)")
        except Exception as exc:                          # pragma: no cover
            self.last_save = {"saved": False, "error": str(exc)}
            log.error("state_save_failed", error=str(exc))
        return self.last_save

    def persistence_status(self) -> dict:
        """화면·API 가 보여줄 영속화 상태."""
        if self.store is None:
            return {
                "enabled": False,
                "backend": "memory",
                "warning": ("영속화가 꺼져 있습니다. "
                            "종료하면 학습 결과가 사라집니다."),
                "error": self._store_error or None,
                "restore": self.restore_report,
            }
        try:
            stats = self.store.stats()
        except Exception as exc:                          # pragma: no cover
            stats = {"error": str(exc)}
        return {
            "enabled": True,
            "autosave_every_ticks": self.autosave_every,
            "store": stats,
            "restore": self.restore_report,
            "last_save": self.last_save,
            "note": ("에이전트가 배운 것(모델 가중치·학습시간·예측 저널)을 "
                     "파일에 저장합니다. API 키는 저장하지 않습니다."),
        }

    def close(self) -> None:
        """종료 직전에 마지막으로 저장하고 저장소를 닫습니다."""
        if self.store is None:
            return
        self.save_state(reason="shutdown")
        try:
            self.store.close()
        except Exception:                                 # pragma: no cover
            pass
        self.store = None

    async def run(self, interval: float = 1.5) -> None:
        self.bus.emit("system.started", is_mock=self.mock_mode,
                      detail="런타임 시작",
                      active_agents=len(self.registry.active()),
                      total_agents=len(self.registry.all()))
        while True:
            self.tick()
            await asyncio.sleep(interval)

    def start(self, interval: float = 1.5) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(interval))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ================================================================== 리서치 잡

    def create_research_job(self, ticker: str, sector: str | None = None) -> dict:
        self._job_seq += 1
        job_id = f"job{self._job_seq:04d}"
        sector = sector or self._guess_sector(ticker)
        job = {
            "job_id": job_id, "ticker": ticker.upper(), "sector": sector,
            "status": "QUEUED", "created_at": datetime.now(timezone.utc).isoformat(),
            "steps": [], "report": None, "is_mock": self.mock_mode,
        }
        self.jobs[job_id] = job
        return job

    def _guess_sector(self, ticker: str) -> str:
        t = ticker.upper()
        for sec, tickers in DEMO_TICKERS.items():
            if t in tickers:
                return sec
        return "semiconductor"

    async def run_research(self, job_id: str) -> dict:
        """Bull/Bear 격리 → 반대근거 강제 → 토론 → Evidence Gate → 판정."""
        job = self.jobs[job_id]
        ticker, sector = job["ticker"], job["sector"]
        job["status"] = "RUNNING"

        def step(name: str, detail: str, **extra):
            entry = {"step": name, "detail": detail,
                     "ts": datetime.now(timezone.utc).isoformat(), **extra}
            job["steps"].append(entry)
            self.bus.emit("job.step", is_mock=self.mock_mode, job_id=job_id,
                          ticker=ticker, step=name, detail=detail, **extra)

        # ---- 1) 라우팅: 필요한 사람만 깨운다 ----
        agents = self.router.select_for_research(sector)
        self.router.wake_count_guard(agents)
        step("ROUTING",
             f"{sector} 섹터 담당 {len(agents)}명을 깨웠습니다 "
             f"(전체 {len(self.registry.all())}명 중)",
             agents=[a.id for a in agents])
        await asyncio.sleep(0.4)

        # ---- 2) 데이터 수집 (Point-in-Time) ----
        series = self.series_for(ticker)
        as_of_index = len(series) - 21          # T 시점
        past = series[: as_of_index + 1]        # ★ 미래는 아예 넘기지 않습니다
        structure = market_structure(past)
        structure["as_of_index"] = as_of_index  # 나중에 이 시점부터 채점합니다
        regime = series_regime(past)
        step("DATA_GATHER",
             f"T 시점까지 {len(past)}봉만 조회 (미래 {len(series) - len(past)}봉은 "
             f"쿼리 자체가 차단됨)",
             point_in_time=True, bars=len(past), regime=regime)
        await asyncio.sleep(0.4)

        # ---- 3) Bull / Bear 독립 분석 (서로의 결과를 볼 수 없음) ----
        bulls = [a for a in agents if a.role == Role.BULL_RESEARCHER]
        bears = [a for a in agents if a.role == Role.BEAR_RESEARCHER]

        bull_ch = self._analyze_side(bulls, ticker, past, structure, "BULL")
        step("BULL_RESEARCH", f"강세 논거 {len(bull_ch['points'])}건 도출 "
                              f"(약세 채널 접근 불가)",
             agents=[a.id for a in bulls])
        await asyncio.sleep(0.3)

        bear_ch = self._analyze_side(bears, ticker, past, structure, "BEAR")
        step("BEAR_RESEARCH", f"약세 논거 {len(bear_ch['points'])}건 도출 "
                              f"(강세 채널 접근 불가)",
             agents=[a.id for a in bears])
        await asyncio.sleep(0.3)

        # ---- 4) 반대 근거 강제 탐색 (§26) ----
        contra_queries = (
            [f"{ticker} {p['key']} 반대 근거" for p in bull_ch["points"][:3]]
            + [f"{ticker} {p['key']} 반박" for p in bear_ch["points"][:3]]
        )
        step("CONTRADICTION_SEARCH",
             f"확증편향 방지: 반대 검색어 {len(contra_queries)}개 자동 생성",
             queries=contra_queries)
        await asyncio.sleep(0.3)

        # ---- 5) 토론 (여기서 처음 서로 공개) ----
        # 픽셀 사무실에서도 실제로 토론실로 이동합니다 (연출이 아니라 상태 변경)
        for a in bulls + bears:
            s = self.states.get(a.id)
            if s:
                self._set_status(s, "DEBATING", f"{ticker} Bull/Bear 토론")
        step("DEBATE", "Bull/Bear 채널을 합쳐 토론 시작", room="Bull / Bear Debate Room")
        await asyncio.sleep(0.5)

        # ---- 6) 근거 계보 + 근거 ID 부여 ----
        # ★ 근거 ID 는 전체에서 유일해야 합니다.
        #   Bull 의 EV001 과 Bear 의 EV001 이 다른 근거를 가리키면
        #   추적이 불가능해집니다.
        tracker = LineageTracker()
        ev_ids: set[str] = set()
        for i, p in enumerate(bull_ch["points"] + bear_ch["points"]):
            eid = f"EV{i + 1:03d}"
            p["evidence_id"] = eid
            ev_ids.add(eid)
            tracker.add(SourceRecord(
                source_id=eid, url=f"internal://chart/{ticker}",
                domain="internal.chart", tier=SourceTier.S,
                title=p["key"], confidence=0.9,
            ))
        lineage = tracker.verdict()
        step("EVIDENCE_LINEAGE",
             f"페이지 {lineage['page_count']}건 → 독립 근거 "
             f"{lineage['independent_evidence_count']}건",
             lineage=lineage)

        # 기술적 상황 자체를 뒷받침하는 근거 (차트 데이터)
        tech_ev = "EV000"
        ev_ids.add(tech_ev)
        tracker.add(SourceRecord(
            source_id=tech_ev, url=f"internal://chart/{ticker}",
            domain="internal.chart", tier=SourceTier.S,
            title="차트 원본 데이터", confidence=0.9,
        ))

        # ---- 7) 리포트 작성 + Evidence Gate ----
        report_body = self._compose_report(
            ticker, structure, bull_ch, bear_ch, regime, tech_ev
        )
        gate = EvidenceGate(known_evidence_ids=ev_ids, strict=True)
        gate_report = gate.check(report_body)
        if not gate_report.passed:
            job["status"] = "BLOCKED"
            step("EVIDENCE_GATE",
                 f"차단됨 — 근거 없는 수치 {len(gate_report.offenders)}건",
                 gate=gate_report.to_dict())
            job["report"] = {"blocked": True, "gate": gate_report.to_dict()}
            return job
        step("EVIDENCE_GATE",
             f"통과 — 수치 {gate_report.checked_numbers}개 전부 근거 ID 보유",
             gate=gate_report.to_dict())

        # ---- 8) 판정 (Evidence Judge → 위원회 → CIO) ----
        judge = self.states.get("evidence_judge")
        if judge and judge.profile.status == AgentStatus.ACTIVE:
            self._set_status(judge, "EVALUATING", f"{ticker} 근거 심사")
        ic = self.states.get("investment_committee")
        if ic and ic.profile.status == AgentStatus.ACTIVE:
            self._set_status(ic, "COMMITTEE", f"{ticker} 투자위원회 심의")
        cio = self.states.get("cio")
        if cio and cio.profile.status == AgentStatus.ACTIVE:
            self._set_status(cio, "CIO_REVIEW", f"{ticker} 최종 검토")
        step("COMMITTEE_REVIEW", "Evidence Judge → 투자위원회 → CIO 검토")
        await asyncio.sleep(0.4)

        bull_score = bull_ch["score"]
        bear_score = bear_ch["score"]
        total = bull_score + bear_score or 1
        verdict = "BULLISH" if bull_score > bear_score * 1.15 else \
                  "BEARISH" if bear_score > bull_score * 1.15 else "NEUTRAL"
        confidence = abs(bull_score - bear_score) / total

        # ---- 9) 예측 저널 기록 ----
        pred = self.journal.record(
            agent_id="investment_committee", ticker=ticker,
            price_at_prediction=past.closes[-1],
            direction="UP" if verdict == "BULLISH" else "DOWN",
            confidence=round(confidence, 3), time_horizon_days=20,
            thesis=f"{verdict} — 강세 {bull_score:.1f} vs 약세 {bear_score:.1f}",
            bull_case="; ".join(p["text"] for p in bull_ch["points"][:3]),
            bear_case="; ".join(p["text"] for p in bear_ch["points"][:3]),
            catalysts=[p["key"] for p in bull_ch["points"][:3]],
            risks=[p["key"] for p in bear_ch["points"][:3]],
            invalidation=f"종가가 지지선 {structure.get('support')} 아래로 마감하면 무효",
            chart_state=structure, market_regime=regime, sector_regime=regime,
            evidence_ids=sorted(ev_ids), is_mock=self.mock_mode,
        )
        step("PREDICTION_JOURNAL", f"예측 {pred.pred_id} 기록 (20일 뒤 자동 채점)",
             pred_id=pred.pred_id)

        job["status"] = "DONE"
        job["report"] = {
            "ticker": ticker, "sector": sector, "verdict": verdict,
            "confidence": round(confidence, 3),
            "bull_score": round(bull_score, 1), "bear_score": round(bear_score, 1),
            "regime": regime,
            "technical": structure,
            "bull_points": bull_ch["points"], "bear_points": bear_ch["points"],
            "contradiction_queries": contra_queries,
            "lineage": lineage,
            "evidence_gate": gate_report.to_dict(),
            "body": report_body,
            "prediction_id": pred.pred_id,
            "participants": [a.id for a in agents],
            "is_mock": self.mock_mode,
            "disclaimer": (
                "이것은 투자 자문이 아닙니다. 현재 데이터는 합성(MOCK) 데이터이며 "
                "실제 시장 데이터가 아닙니다."
            ),
        }
        self.bus.emit("job.done", is_mock=self.mock_mode, job_id=job_id,
                      ticker=ticker, verdict=verdict,
                      detail=f"{ticker} 리서치 완료: {verdict}")
        return job

    # ------------------------------------------------------------------
    def _analyze_side(self, agents, ticker, past, structure, side) -> dict:
        """한쪽 진영의 독립 분석. 상대 채널은 인자로도 들어오지 않습니다."""
        points: list[dict] = []
        score = 0.0
        s = structure

        checks_bull = [
            ("추세", s.get("trend") == "uptrend",
             "고점·저점이 higher high / higher low 구조", 2.0),
            ("이동평균", bool(s.get("above_sma20")),
             f"종가가 20일 이동평균 위 (SMA20 {s.get('sma20')})", 1.5),
            ("돌파", bool(s.get("breakout")),
             f"저항선 {s.get('resistance')} 부근 돌파 시도", 2.0),
            ("추세강도", (s.get("adx14") or 0) > 25,
             f"ADX {s.get('adx14')} 로 추세가 살아 있음", 1.2),
            ("거래량", (s.get("rvol20") or 0) > 1.2,
             f"상대 거래량 {s.get('rvol20')} 배로 관심 유입", 1.0),
        ]
        checks_bear = [
            ("추세", s.get("trend") == "downtrend",
             "고점·저점이 lower high / lower low 구조", 2.0),
            ("이동평균", not s.get("above_sma20"),
             f"종가가 20일 이동평균 아래 (SMA20 {s.get('sma20')})", 1.5),
            ("이탈", bool(s.get("breakdown")),
             f"지지선 {s.get('support')} 이탈 위험", 2.0),
            ("과열", (s.get("rsi14") or 50) > 70,
             f"RSI {s.get('rsi14')} 로 단기 과열", 1.3),
            ("변동성", (s.get("atr_pct") or 0) > 4,
             f"ATR이 가격의 {s.get('atr_pct')}% 로 변동성 과다", 1.2),
        ]
        checks = checks_bull if side == "BULL" else checks_bear

        for key, cond, text, w in checks:
            if cond:
                points.append({"key": key, "text": text, "weight": w})
                score += w

        # 에이전트 자신의 학습된 모델 의견을 반영
        for a in agents:
            st = self.states.get(a.id)
            if st is None:
                continue
            from packages.learning_engine.features import extract_features
            x = extract_features(past)
            if x is None:
                continue
            direction, conf = st.model.predict(x)
            agrees = (direction == "UP") if side == "BULL" else (direction == "DOWN")
            if agrees:
                score += conf * 2.0
                points.append({
                    "key": f"{a.name} 모델",
                    "text": f"{a.name} 의 학습 모델이 {direction} 를 확신도 "
                            f"{conf:.2f} 로 지지 (표본 {st.model.samples_seen}건, "
                            f"차트점수 {st.model.chart_skill_score()})",
                    "weight": round(conf * 2.0, 2),
                    "agent_id": a.id,
                })
            st.ticker = ticker
            st.position = side
            st.confidence = conf

        return {"points": points, "score": score, "side": side}

    def _compose_report(self, ticker, s, bull, bear, regime, tech_ev: str) -> str:
        """모든 수치에 근거 ID 를 붙입니다. 없으면 Evidence Gate 에서 막힙니다."""
        def cite(p: dict) -> str:
            return f"- {p['text']} [E:{p.get('evidence_id', 'MISSING')}]"

        lines = [
            f"# {ticker} 리서치 리포트 (MOCK DATA)",
            "",
            f"시장 국면: {regime}",
            "",
            "## 기술적 상황",
            f"- 추세: {s.get('trend')}",
            f"- 지지: {s.get('support')} / 저항: {s.get('resistance')} [E:{tech_ev}]",
            f"- RSI14: {s.get('rsi14')} / ADX14: {s.get('adx14')} [E:{tech_ev}]",
            "",
            "## 강세 논거",
        ]
        lines += [cite(p) for p in bull["points"]] or ["- 확인된 강세 논거 없음"]
        lines += ["", "## 약세 논거"]
        lines += [cite(p) for p in bear["points"]] or ["- 확인된 약세 논거 없음"]
        lines += [
            "",
            "## 한계",
            "- 현재 데이터는 합성(MOCK)이며 실제 시장 데이터가 아닙니다.",
            "- 근거 ID 가 없는 수치는 이 리포트에 포함될 수 없습니다 (Evidence Gate).",
            "- 기술적 신호는 통계적 경향이며 확정 예측이 아닙니다.",
        ]
        return "\n".join(lines)

    # ================================================================== 백테스트

    STRATEGIES = {
        "sma_crossover": "SMA 20/50 교차",
        "buy_and_hold": "매수 후 보유",
        "flat": "현금 보유 (대조군)",
    }

    def run_backtest(self, ticker: str, strategy_name: str = "sma_crossover",
                     commission_bps: float = 5.0, slippage_bps: float = 5.0) -> dict:
        """백테스트 실행. Chart Lab / Backtest Lab 의 에이전트 상태도 함께 바꿉니다."""
        from packages.backtest_engine.engine import (
            BacktestEngine,
            Signal,
            buy_and_hold_strategy,
            sma_crossover_strategy,
        )

        ticker = ticker.upper()
        if strategy_name not in self.STRATEGIES:
            raise ValueError(
                f"알 수 없는 전략: {strategy_name} "
                f"(가능: {', '.join(self.STRATEGIES)})"
            )

        strategy = {
            "sma_crossover": lambda: sma_crossover_strategy(),
            "buy_and_hold": lambda: buy_and_hold_strategy(),
            "flat": lambda: (lambda past, w: Signal(0.0, "현금")),
        }[strategy_name]()

        series = self.series_for(ticker, length=600)
        bench = self.series_for("__BENCH__", length=600)

        # 퀀트/기술 담당을 Backtest Lab 으로 보냅니다 (연출이 아니라 실제 작업)
        for st in self.states.values():
            if st.profile.status == AgentStatus.ACTIVE and st.profile.role in (
                Role.QUANT_MASTER, Role.TECHNICAL_MASTER,
            ):
                self._set_status(st, "BACKTESTING", f"{ticker} 백테스트 ({strategy_name})")

        engine = BacktestEngine(commission_bps=commission_bps,
                                slippage_bps=slippage_bps, warmup=60)
        result = engine.run(series, strategy, benchmark=bench)

        payload = {
            "ticker": ticker,
            "strategy": strategy_name,
            "strategy_label": self.STRATEGIES[strategy_name],
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "is_mock": self.mock_mode,
            **result.to_dict(),
            "disclaimer": (
                "합성(MOCK) 데이터 기반입니다. 실제 시장 성과가 아니며 "
                "투자 판단의 근거로 쓸 수 없습니다."
            ),
        }
        self.bus.emit("backtest.done", is_mock=self.mock_mode, ticker=ticker,
                      strategy=strategy_name,
                      detail=f"{ticker} 백테스트 완료 "
                             f"(Sharpe {payload['metrics'].get('sharpe')})")
        return payload

    # ================================================================== 패턴 마이닝

    def mine_patterns(self, horizon: int = 5, force: bool = False) -> dict:
        """패턴 탐색. 비용이 있으므로 결과를 캐시합니다."""
        from packages.pattern_miner.miner import PatternMiner

        cache_key = f"h{horizon}"
        if not force and cache_key in self._pattern_cache:
            return self._pattern_cache[cache_key]

        datasets = {
            t: self.series_for(t, length=800)
            for t in ["NVDA", "AMD", "AVGO", "MRNA", "XOM", "CEG"]
        }
        miner = PatternMiner(horizon=horizon, max_conditions=2)
        patterns = miner.mine(datasets)
        summary = PatternMiner.summary(
            patterns,
            data_source="MOCK_SYNTHETIC" if self.mock_mode else "MARKET",
            horizon=horizon,
            correction=miner.last_correction,      # ★ 다중검정 보정 결과
        )
        summary["all_patterns"] = [p.to_dict() for p in patterns[:60]]
        self._pattern_cache[cache_key] = summary
        self.bus.emit("patterns.mined", is_mock=self.mock_mode,
                      detail=f"패턴 {summary['candidates_tested']}개 검증 → "
                             f"STRONG {summary['by_verdict'].get('STRONG', 0)}개")
        return summary

    # ================================================================== 요약

    def system_health(self) -> dict:
        active = self.registry.active()
        by_status: dict[str, int] = {}
        for st in self.states.values():
            if st.profile.status == AgentStatus.ACTIVE:
                by_status[st.status] = by_status.get(st.status, 0) + 1
        total_effective = sum(
            st.tracker.effective_seconds for st in self.states.values()
        )
        return {
            "mock_mode": self.mock_mode,
            # ★ 화면 배지가 매 틱 이 값으로 갱신되므로 여기에도 반드시 넣습니다.
            #   빠뜨리면 실데이터가 있어도 화면이 MOCK 으로 되돌아갑니다.
            "data_mode": self.data_mode(),
            "real_symbols": sorted(self.real_symbols),
            "persistence_enabled": self.store is not None,
            "uptime_seconds": int(
                (datetime.now(timezone.utc) - self.started_at).total_seconds()
            ),
            "learning_day": self.day,
            "ticks": self.tick_count,
            "agents_total": len(self.registry.all()),
            "agents_active": len(active),
            "agents_by_status": by_status,
            "researching": by_status.get("RESEARCHING", 0) + by_status.get("READING", 0),
            "learning": by_status.get("CHARTING", 0) + by_status.get("LEARNING", 0),
            "blocked": by_status.get("BLOCKED", 0),
            "jobs_queued": sum(1 for j in self.jobs.values() if j["status"] == "QUEUED"),
            "jobs_running": sum(1 for j in self.jobs.values() if j["status"] == "RUNNING"),
            "knowledge": self.knowledge.stats(),
            "predictions": len(self.journal.predictions),
            "total_effective_learning_hours": round(total_effective / 3600, 2),
            "ws_subscribers": self.bus.subscriber_count,
            "events_emitted": self.bus.total_emitted,
            "llm_calls": 0,
            "llm_cost_usd": round(sum(self.cost_ledger.values()), 4),
            "llm_note": "LLM 미연결 상태입니다. 학습과 검증은 로컬 계산으로 동작 중입니다.",
            # ★ 정직성: 이 숫자가 실제 벽시계 시간이 아니라는 걸 명시합니다.
            "time_scale": "ACCELERATED_SIMULATION",
            "time_scale_note": (
                "학습시간은 가속 시뮬레이션 값입니다. 1틱마다 학습 단계가 "
                "하나씩 진행되며, 실제 경과 시간과 다릅니다. "
                f"현재 {self.tick_count}틱 = 학습 {self.day}일차."
            ),
        }
