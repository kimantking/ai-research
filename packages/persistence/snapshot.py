"""엔진 상태 스냅샷 — 껐다 켜도 학습이 이어지게 합니다.

★ 무엇을 저장하는가

    저장한다            이유
    ─────────────────   ────────────────────────────────────────────
    모델 가중치          이게 곧 '에이전트가 배운 것' 입니다
    학습 통계            정확도·캘리브레이션·표본 수
    누적 학습 시간        "오늘 4시간" 이 재시작으로 리셋되면 안 됩니다
    예측 저널            과거 예측을 복기해야 Trust Score 가 쌓입니다
    지식 저장소           검증을 통과한 사실
    카운터·경과일         며칠째 일하고 있는지

    저장하지 않는다      이유
    ─────────────────   ────────────────────────────────────────────
    현재 위치·상태        재시작하면 어차피 새 하루가 시작됩니다
    합성 시세 캐시        시드로 언제든 똑같이 다시 만듭니다
    API 키·비밀번호       ★ 절대 저장하지 않습니다
    실행 중 작업(job)     끊긴 작업을 되살리면 더 헷갈립니다

★ 복구 원칙

    스냅샷이 깨져 있거나 형식이 달라도 **시스템은 반드시 뜹니다.**
    복구는 항목별로 시도하고, 실패한 항목은 건너뛰고 이유를 남깁니다.
    "저장소 때문에 프로그램이 안 켜진다" 는 최악입니다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

NAMESPACE_AGENT = "agent_state"
NAMESPACE_ENGINE = "engine"
SNAPSHOT_FORMAT = 2


@dataclass
class EngineSnapshot:
    saved_at: float = 0.0
    format: int = SNAPSHOT_FORMAT
    agents_saved: int = 0
    predictions_saved: int = 0
    prediction_results_saved: int = 0
    knowledge_saved: int = 0
    knowledge_rejected_saved: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "saved_at": self.saved_at,
            "format": self.format,
            "agents_saved": self.agents_saved,
            "predictions_saved": self.predictions_saved,
            "prediction_results_saved": self.prediction_results_saved,
            "knowledge_saved": self.knowledge_saved,
            "knowledge_rejected_saved": self.knowledge_rejected_saved,
            "errors": self.errors,
        }


# ------------------------------------------------------------------ 저장
def _agent_payload(st) -> dict:
    """한 에이전트에서 '배운 것' 만 뽑아냅니다."""
    m = st.model
    tr = st.tracker
    return {
        "model": {
            "weights": list(m.weights),
            "samples_seen": m.samples_seen,
            "correct": m.correct,
            "recent": list(m.recent)[-m.recent_window:],
            "calib_bins": [list(b) for b in m.calib_bins],
            "role_prior": m.role_prior,
        },
        "tracker": {
            "effective_seconds": tr.effective_seconds,
            "wasted_seconds": tr.wasted_seconds,
            "by_activity": dict(tr.by_activity),
            "wasted_by_reason": dict(tr.wasted_by_reason),
        },
        "counters": {
            "sources_read": st.sources_read,
            "sources_rejected": st.sources_rejected,
            "knowledge_added": st.knowledge_added,
            "knowledge_rejected": st.knowledge_rejected,
            "chart_exercises": st.chart_exercises,
            "prediction_reviews": st.prediction_reviews,
        },
        "scores": {
            "last_exam_score": st.last_exam_score,
            "last_source_exam_score": st.last_source_exam_score,
            "sector_knowledge_score": st.sector_knowledge_score,
        },
    }


def snapshot_engine(engine, store) -> EngineSnapshot:
    """엔진의 학습 성과를 저장소에 씁니다. 실패해도 예외를 밖으로 던지지 않습니다."""
    snap = EngineSnapshot(saved_at=time.time())
    if store is None:
        snap.errors.append("저장소가 없습니다 (메모리 전용 모드)")
        return snap

    # 1) 에이전트 — 한 번에 묶어서 씁니다
    try:
        payload = {aid: _agent_payload(st) for aid, st in engine.states.items()
                   if st.model.samples_seen > 0 or st.tracker.effective_seconds > 0}
        if payload:
            store.put_many_kv(NAMESPACE_AGENT, payload)
        snap.agents_saved = len(payload)
    except Exception as exc:                              # pragma: no cover
        snap.errors.append(f"에이전트 저장 실패: {exc}")

    # 2) 예측 저널
    try:
        preds = [p.to_dict() for p in engine.journal.predictions.values()]
        results = {
            pid: [r.to_dict() for r in rs]
            for pid, rs in getattr(engine.journal, "results", {}).items()
        }
        store.put_kv(NAMESPACE_ENGINE, "predictions", preds)
        store.put_kv(NAMESPACE_ENGINE, "prediction_results", results)
        store.upsert_predictions(preds)
        snap.predictions_saved = len(preds)
        snap.prediction_results_saved = sum(len(v) for v in results.values())
    except Exception as exc:                              # pragma: no cover
        snap.errors.append(f"예측 저장 실패: {exc}")

    # 3) 지식 — 승인된 것과 **기각된 것 모두**.
    #    기각 이력을 잃으면 같은 루머를 매번 새로 검증하게 됩니다(§감사 추적).
    try:
        from dataclasses import asdict
        approved = [asdict(v) for v in engine.knowledge.approved.values()]
        rejected = [asdict(v) for v in engine.knowledge.rejected]
        store.put_kv(NAMESPACE_ENGINE, "knowledge", approved)
        store.put_kv(NAMESPACE_ENGINE, "knowledge_rejected", rejected)
        snap.knowledge_saved = len(approved)
        snap.knowledge_rejected_saved = len(rejected)
    except Exception as exc:                              # pragma: no cover
        snap.errors.append(f"지식 저장 실패: {exc}")

    # 4) 엔진 메타
    try:
        store.put_kv(NAMESPACE_ENGINE, "meta", {
            "format": SNAPSHOT_FORMAT,
            "saved_at": snap.saved_at,
            "day": engine.day,
            "tick_count": engine.tick_count,
            "mock_mode": engine.mock_mode,
            "cost_ledger": dict(engine.cost_ledger),
        })
    except Exception as exc:                              # pragma: no cover
        snap.errors.append(f"메타 저장 실패: {exc}")

    return snap


# ------------------------------------------------------------------ 복구
def restore_engine(engine, store) -> dict:
    """저장된 학습 성과를 엔진에 되돌립니다.

    ★ 어떤 항목이 깨져 있어도 시스템은 반드시 뜹니다.
    """
    report = {
        "restored": False,
        "agents_restored": 0,
        "predictions_restored": 0,
        "prediction_results_restored": 0,
        "knowledge_restored": 0,
        "day": 0,
        "errors": [],
        "note": "",
    }
    if store is None:
        report["note"] = "저장소가 없습니다 — 메모리 전용으로 시작합니다."
        return report

    # 1) 메타
    meta = {}
    try:
        meta = store.get_kv(NAMESPACE_ENGINE, "meta", {}) or {}
        if meta.get("format") not in (None, SNAPSHOT_FORMAT):
            report["errors"].append(
                f"스냅샷 형식 {meta.get('format')} — 현재 {SNAPSHOT_FORMAT}. "
                "호환되는 부분만 복구합니다."
            )
        engine.day = int(meta.get("day", 0) or 0)
        engine.cost_ledger.update(meta.get("cost_ledger", {}) or {})
        report["day"] = engine.day
    except Exception as exc:
        report["errors"].append(f"메타 복구 실패: {exc}")

    # 2) 에이전트
    try:
        saved = store.list_kv(NAMESPACE_AGENT)
        for aid, data in saved.items():
            st = engine.states.get(aid)
            if st is None:
                continue
            try:
                _restore_agent(st, data)
                report["agents_restored"] += 1
            except Exception as exc:
                report["errors"].append(f"{aid} 복구 실패: {exc}")
    except Exception as exc:
        report["errors"].append(f"에이전트 목록 복구 실패: {exc}")

    # 3) 예측 (+ 채점 결과)
    try:
        preds = store.get_kv(NAMESPACE_ENGINE, "predictions", []) or []
        report["predictions_restored"] = _restore_predictions(engine.journal, preds)
        results = store.get_kv(NAMESPACE_ENGINE, "prediction_results", {}) or {}
        report["prediction_results_restored"] = _restore_prediction_results(
            engine.journal, results)
    except Exception as exc:
        report["errors"].append(f"예측 복구 실패: {exc}")

    # 4) 지식 (승인 + 기각)
    try:
        engine.restored_knowledge = store.get_kv(
            NAMESPACE_ENGINE, "knowledge", []) or []
        engine.restored_knowledge_rejected = store.get_kv(
            NAMESPACE_ENGINE, "knowledge_rejected", []) or []
        report["knowledge_restored"] = len(engine.restored_knowledge)
    except Exception as exc:
        report["errors"].append(f"지식 복구 실패: {exc}")

    report["restored"] = bool(
        report["agents_restored"] or report["predictions_restored"])
    report["note"] = (
        f"이전 실행에서 이어집니다 (에이전트 {report['agents_restored']}명, "
        f"예측 {report['predictions_restored']}건, {report['day']}일차)."
        if report["restored"] else
        "저장된 상태가 없습니다 — 처음부터 시작합니다."
    )
    return report


def _restore_agent(st, data: dict) -> None:
    m = data.get("model") or {}
    weights = m.get("weights")
    if isinstance(weights, list) and len(weights) == len(st.model.weights):
        st.model.weights = [float(w) for w in weights]
    st.model.samples_seen = int(m.get("samples_seen", 0) or 0)
    st.model.correct = int(m.get("correct", 0) or 0)
    recent = m.get("recent")
    if isinstance(recent, list):
        st.model.recent = [int(bool(v)) for v in recent][-st.model.recent_window:]
    bins = m.get("calib_bins")
    if isinstance(bins, list) and len(bins) == len(st.model.calib_bins):
        st.model.calib_bins = [[int(a), int(b)] for a, b in bins]

    t = data.get("tracker") or {}
    st.tracker.effective_seconds = float(t.get("effective_seconds", 0.0) or 0.0)
    st.tracker.wasted_seconds = float(t.get("wasted_seconds", 0.0) or 0.0)
    if isinstance(t.get("by_activity"), dict):
        st.tracker.by_activity = {k: float(v) for k, v in t["by_activity"].items()}
    if isinstance(t.get("wasted_by_reason"), dict):
        st.tracker.wasted_by_reason = {
            k: float(v) for k, v in t["wasted_by_reason"].items()}

    c = data.get("counters") or {}
    for name in ("sources_read", "sources_rejected", "knowledge_added",
                 "knowledge_rejected", "chart_exercises", "prediction_reviews"):
        if name in c:
            setattr(st, name, int(c[name] or 0))

    s = data.get("scores") or {}
    if s.get("last_exam_score") is not None:
        st.last_exam_score = s["last_exam_score"]
    if s.get("last_source_exam_score") is not None:
        st.last_source_exam_score = s["last_source_exam_score"]
    if s.get("sector_knowledge_score") is not None:
        st.sector_knowledge_score = float(s["sector_knowledge_score"])


def _restore_predictions(journal, preds: list[dict]) -> int:
    """저널을 복구합니다. 형식이 다른 항목은 조용히 건너뜁니다."""
    from packages.evaluation.journal import Prediction

    if not isinstance(preds, list):
        return 0
    fields = set(Prediction.__dataclass_fields__)
    n = 0
    max_seq = journal._seq
    for row in preds:
        if not isinstance(row, dict):
            continue
        kwargs = {k: v for k, v in row.items() if k in fields}
        if not kwargs.get("pred_id"):
            continue
        rng = kwargs.get("expected_range")
        if isinstance(rng, list) and len(rng) == 2:
            kwargs["expected_range"] = (rng[0], rng[1])
        try:
            p = Prediction(**kwargs)
        except (TypeError, ValueError):
            continue
        journal.predictions[p.pred_id] = p
        n += 1
        # 새 예측 ID 가 옛 것과 부딪히지 않도록 시퀀스를 앞당깁니다.
        if p.pred_id.startswith("p") and p.pred_id[1:].isdigit():
            max_seq = max(max_seq, int(p.pred_id[1:]))
    journal._seq = max_seq
    return n


def _restore_prediction_results(journal, saved: dict) -> int:
    """채점 결과까지 복구해야 Trust Score 가 이어집니다."""
    from packages.evaluation.journal import PredictionResult

    if not isinstance(saved, dict):
        return 0
    fields = set(PredictionResult.__dataclass_fields__)
    n = 0
    for pid, rows in saved.items():
        if pid not in journal.predictions or not isinstance(rows, list):
            continue
        restored = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            kwargs = {k: v for k, v in row.items() if k in fields}
            try:
                restored.append(PredictionResult(**kwargs))
                n += 1
            except (TypeError, ValueError):
                continue
        if restored:
            journal.results[pid] = restored
    return n
