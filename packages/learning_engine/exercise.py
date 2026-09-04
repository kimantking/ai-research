"""차트 학습 문제 — 미래를 가리고, 예측하고, 공개하고, 채점한다.

절차 (프로젝트 원칙 §37)
    1) 과거 OHLCV 윈도우를 만든다
    2) T 시점 이후는 '함수에 넘기지 않는다'  ← 구조적 차단
    3) 에이전트가 1D/5D/20D 전망을 낸다
    4) 미래를 공개한다
    5) 예측 vs 실제 비교
    6) 실패 분석 → 가중치 갱신
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.chart_skills.series import OHLCV
from packages.chart_skills.structure import market_structure

from .features import MIN_BARS, extract_features
from .model import OnlineChartModel

HORIZONS = (1, 5, 20)


@dataclass
class ChartExercise:
    """한 문제.

    past 에는 T 시점까지만 들어 있습니다.
    future 는 채점할 때만 씁니다 — 에이전트에게 전달되는 컨텍스트에는
    절대 포함되지 않습니다.
    """

    exercise_id: str
    symbol: str
    cut_index: int
    past: OHLCV
    _future: OHLCV = field(repr=False)
    horizon: int = 5

    # ---- 에이전트에게 주는 것 (미래 없음) ----
    def agent_context(self) -> dict:
        """§38 — 이미지가 아니라 '숫자'를 함께 준다."""
        return {
            "exercise_id": self.exercise_id,
            "symbol": self.symbol,
            "horizon_days": self.horizon,
            "bars_visible": len(self.past),
            "recent_candles": self.past[-30:].to_list(),
            "structure": market_structure(self.past),
            "is_mock": True,
        }

    # ---- 채점용 (에이전트에게 노출 금지) ----
    def realized_return(self) -> float | None:
        if len(self._future) < self.horizon:
            return None
        start = self.past.closes[-1]
        end = self._future.closes[self.horizon - 1]
        return (end - start) / start

    def realized_path(self) -> dict:
        """MAE/MFE — 얼마나 흔들렸는지. 방향만 보면 안 되기 때문에 (§34)."""
        if len(self._future) < self.horizon:
            return {}
        start = self.past.closes[-1]
        window = self._future[: self.horizon]
        mfe = (max(window.highs) - start) / start
        mae = (min(window.lows) - start) / start
        return {"mfe": round(mfe, 5), "mae": round(mae, 5)}


def build_exercise(
    series: OHLCV, cut_index: int, symbol: str, horizon: int = 5, exercise_id: str = ""
) -> ChartExercise | None:
    """T=cut_index 에서 시계열을 자릅니다.

    past  = series[:cut_index+1]   (T 시점까지 = 그때 실제로 알 수 있던 것)
    future = series[cut_index+1:]  (채점 전용)
    """
    if cut_index < MIN_BARS:
        return None
    if cut_index + horizon >= len(series):
        return None
    return ChartExercise(
        exercise_id=exercise_id or f"{symbol}-{cut_index}-{horizon}",
        symbol=symbol,
        cut_index=cut_index,
        past=series[: cut_index + 1],
        _future=series[cut_index + 1 :],
        horizon=horizon,
    )


def evaluate_exercise(model: OnlineChartModel, ex: ChartExercise, learn: bool = True) -> dict:
    """예측 → 공개 → 채점 → (학습 모드면) 가중치 갱신.

    learn=False 는 시험(out-of-sample)용입니다. 시험 문제로 공부하면
    점수가 부풀려집니다 (§40 과적합 방지).
    """
    x = extract_features(ex.past)
    if x is None:
        return {"skipped": True, "reason": "데이터 부족"}

    direction, confidence = model.predict(x)
    realized = ex.realized_return()
    if realized is None:
        return {"skipped": True, "reason": "미래 구간 부족"}

    label = 1 if realized > 0 else 0
    actual_dir = "UP" if label == 1 else "DOWN"
    correct = direction == actual_dir

    result = {
        "exercise_id": ex.exercise_id,
        "symbol": ex.symbol,
        "horizon": ex.horizon,
        "predicted": direction,
        "confidence": round(confidence, 3),
        "actual": actual_dir,
        "actual_return_pct": round(realized * 100, 3),
        "correct": correct,
        "learned": learn,
        **ex.realized_path(),
    }

    if learn:
        upd = model.update(x, label)
        result["probability"] = upd["probability"]
        # 오답 분석 (§35 의 축소판 — 무엇이 어긋났는지 분류)
        if not correct:
            result["failure_category"] = _classify_failure(ex, realized, confidence)

    return result


def _classify_failure(ex: ChartExercise, realized: float, confidence: float) -> str:
    """왜 틀렸는지 분류. 나중에 LLM 이 붙으면 더 정교해집니다."""
    st = market_structure(ex.past)
    atr_pct = st.get("atr_pct") or 2.0
    move_pct = abs(realized * 100)

    if confidence > 0.6:
        return "OVERCONFIDENCE"
    if move_pct > atr_pct * 3:
        return "VOLATILITY_SHOCK"
    if st.get("breakout") and realized < 0:
        return "FAILED_BREAKOUT"
    if st.get("breakdown") and realized > 0:
        return "FAILED_BREAKDOWN"
    if move_pct < atr_pct * 0.3:
        return "NOISE_LEVEL_MOVE"
    if st.get("trend") == "range":
        return "RANGE_WHIPSAW"
    return "TREND_REVERSAL"
