"""Prediction Journal — 모든 투자 판단을 기록하고 나중에 채점합니다.

프로젝트 원칙 §33~36
    판단을 내렸으면 반드시 기록하고, 1D/5D/20D/60D 뒤에 채점하고,
    틀렸으면 왜 틀렸는지 분류해서 학습에 반영합니다.

    맞고 틀림만 보지 않습니다:
      방향 정확도 / 수익률 오차 / 확신도 캘리브레이션 /
      MAE(최대 역행) / MFE(최대 순행) / 논리 유효성 / 타이밍
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

HORIZONS = (1, 5, 20, 60)


@dataclass
class Prediction:
    pred_id: str
    agent_id: str
    ticker: str
    ts: str
    price_at_prediction: float
    direction: str                    # UP | DOWN
    confidence: float                 # 0~1
    time_horizon_days: int
    expected_range: tuple[float, float] | None = None
    thesis: str = ""
    bull_case: str = ""
    bear_case: str = ""
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    invalidation: str = ""
    chart_state: dict = field(default_factory=dict)
    market_regime: str = "unknown"
    sector_regime: str = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    is_mock: bool = True

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["expected_range"] = list(self.expected_range) if self.expected_range else None
        return d


@dataclass
class PredictionResult:
    pred_id: str
    horizon: int
    actual_return: float
    direction_correct: bool
    return_error: float
    mae: float
    mfe: float
    calibration_error: float
    failure_category: str | None = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class PredictionJournal:
    def __init__(self, max_predictions: int = 2000) -> None:
        self.predictions: dict[str, Prediction] = {}
        self.results: dict[str, list[PredictionResult]] = {}
        self._seq = 0
        # 오래 돌려도 메모리가 무한히 늘지 않도록 상한을 둡니다.
        # (Phase 5에서 DB 로 옮기면 이 상한은 사라집니다)
        self.max_predictions = max_predictions

    # ------------------------------------------------------------------
    def record(self, **kwargs) -> Prediction:
        self._seq += 1
        pred = Prediction(
            pred_id=kwargs.pop("pred_id", f"p{self._seq:06d}"),
            ts=kwargs.pop("ts", datetime.now(timezone.utc).isoformat()),
            **kwargs,
        )
        self.predictions[pred.pred_id] = pred
        self._trim()
        return pred

    def _trim(self) -> None:
        while len(self.predictions) > self.max_predictions:
            oldest = next(iter(self.predictions))
            self.predictions.pop(oldest, None)
            self.results.pop(oldest, None)

    # ------------------------------------------------------------------
    def evaluate(
        self,
        pred_id: str,
        horizon: int,
        closes_after: list[float],
        highs_after: list[float] | None = None,
        lows_after: list[float] | None = None,
    ) -> PredictionResult | None:
        """예측 이후 실제 가격으로 채점합니다."""
        pred = self.predictions.get(pred_id)
        if pred is None or len(closes_after) < horizon:
            return None

        start = pred.price_at_prediction
        end = closes_after[horizon - 1]
        actual = (end - start) / start

        window_h = (highs_after or closes_after)[:horizon]
        window_l = (lows_after or closes_after)[:horizon]
        mfe = (max(window_h) - start) / start
        mae = (min(window_l) - start) / start

        predicted_up = pred.direction == "UP"
        correct = predicted_up == (actual > 0)

        # 확신도 캘리브레이션: 90% 확신했는데 틀리면 큰 벌점
        calib_err = abs((0.5 + pred.confidence / 2) - (1.0 if correct else 0.0))

        expected_mid = 0.0
        if pred.expected_range:
            expected_mid = sum(pred.expected_range) / 2 / 100.0
        return_error = abs(actual - expected_mid)

        res = PredictionResult(
            pred_id=pred_id,
            horizon=horizon,
            actual_return=round(actual, 5),
            direction_correct=correct,
            return_error=round(return_error, 5),
            mae=round(mae, 5),
            mfe=round(mfe, 5),
            calibration_error=round(calib_err, 4),
            failure_category=None if correct else classify_failure(pred, actual, mae, mfe),
        )
        # 같은 예측을 같은 기간으로 다시 채점하면 '덮어씁니다'.
        # 새 줄을 추가하면 복기할 때마다 성적표가 부풀려집니다.
        bucket = self.results.setdefault(pred_id, [])
        for i, existing in enumerate(bucket):
            if existing.horizon == horizon:
                bucket[i] = res
                return res
        bucket.append(res)
        return res

    # ------------------------------------------------------------------
    def agent_stats(self, agent_id: str) -> dict:
        preds = [p for p in self.predictions.values() if p.agent_id == agent_id]
        results = [r for p in preds for r in self.results.get(p.pred_id, [])]
        if not results:
            return {
                "agent_id": agent_id, "predictions": len(preds), "evaluated": 0,
                "direction_accuracy_pct": None, "avg_calibration_error": None,
                "trust_score": None,
                "note": "아직 채점된 예측이 없습니다 (평가 시점 미도래)",
            }
        acc = sum(r.direction_correct for r in results) / len(results)
        avg_mae = sum(r.mae for r in results) / len(results)

        # 캘리브레이션은 구간별(ECE)로 계산합니다.
        # "80% 확신"이라고 말했으면 그 구간에서 실제로 80% 맞아야 정직한 것입니다.
        # 예측 하나하나의 오차를 평균하면 동전던지기도 0.5가 나와서 의미가 없습니다.
        bins: list[list[float]] = [[0.0, 0.0] for _ in range(5)]
        for r in results:
            p = self.predictions[r.pred_id]
            b = min(4, int(p.confidence * 5))
            bins[b][0] += 1
            bins[b][1] += 1.0 if r.direction_correct else 0.0
        total_n = sum(b[0] for b in bins) or 1
        calib = 0.0
        for i, (n, hit) in enumerate(bins):
            if n == 0:
                continue
            expected = 0.5 + (i + 0.5) / 5.0 * 0.5   # 구간 중앙의 기대 적중률
            calib += (n / total_n) * abs(expected - hit / n)

        # Trust Score: 정확도 + 정직함(캘리브레이션) + 표본 성숙도
        maturity = min(1.0, len(results) / 50.0)
        trust = max(0.0, min(100.0, ((acc - 0.5) * 200 * 0.5 + 50) - calib * 60)) * (0.6 + 0.4 * maturity)

        cats: dict[str, int] = {}
        for r in results:
            if r.failure_category:
                cats[r.failure_category] = cats.get(r.failure_category, 0) + 1

        return {
            "agent_id": agent_id,
            "predictions": len(preds),
            "evaluated": len(results),
            "direction_accuracy_pct": round(acc * 100, 1),
            "avg_calibration_error": round(calib, 4),
            "avg_max_adverse_excursion_pct": round(avg_mae * 100, 2),
            "trust_score": round(trust, 1),
            "failure_categories": cats,
        }


def classify_failure(pred: Prediction, actual: float, mae: float, mfe: float) -> str:
    """왜 틀렸는지 분류 (§35). LLM 이 붙으면 더 정교해집니다."""
    atr_pct = (pred.chart_state or {}).get("atr_pct") or 2.0
    move = abs(actual) * 100

    if pred.confidence > 0.7:
        return "OVERCONFIDENCE"
    if move > atr_pct * 3:
        return "VOLATILITY_SHOCK"
    if (pred.chart_state or {}).get("breakout") and actual < 0:
        return "TECHNICAL_FAILURE_FAILED_BREAKOUT"
    if (pred.chart_state or {}).get("breakdown") and actual > 0:
        return "TECHNICAL_FAILURE_FAILED_BREAKDOWN"
    if pred.direction == "UP" and mfe > abs(actual) * 2:
        return "TIMING_ERROR"     # 방향은 맞았는데 타이밍이 늦음
    if move < atr_pct * 0.3:
        return "NOISE_LEVEL_MOVE"
    if (pred.chart_state or {}).get("trend") == "range":
        return "RANGE_WHIPSAW"
    return "TREND_REVERSAL"
