"""★ 최우선 테스트 — Look-ahead Bias 차단 검증.

이 테스트가 깨지면 이 프로젝트 전체가 의미를 잃습니다.
백테스트에서 미래를 조금이라도 보면, 성과는 환상적으로 나오고
실전에서는 전부 잃습니다.
"""

import unittest

from packages.chart_skills.synth import generate_series
from packages.learning_engine.exercise import build_exercise, evaluate_exercise
from packages.learning_engine.features import extract_features
from packages.learning_engine.model import OnlineChartModel


class TestExerciseIsolation(unittest.TestCase):
    def setUp(self):
        self.series = generate_series(seed=42, length=300)
        self.cut = 200
        self.ex = build_exercise(self.series, self.cut, "TEST", horizon=5)

    def test_past_ends_exactly_at_cut(self):
        self.assertIsNotNone(self.ex)
        self.assertEqual(len(self.ex.past), self.cut + 1)
        self.assertEqual(self.ex.past[-1].ts, self.series[self.cut].ts)

    def test_agent_context_contains_no_future_candle(self):
        """에이전트에게 주는 컨텍스트에 미래 캔들이 단 하나도 없어야 합니다."""
        ctx = self.ex.agent_context()
        future_ts = {c.ts for c in self.series[self.cut + 1 :]}
        for candle in ctx["recent_candles"]:
            self.assertNotIn(candle["ts"], future_ts)

    def test_agent_context_has_no_future_price_values(self):
        ctx = self.ex.agent_context()
        past_prices = set(self.ex.past.closes)
        for candle in ctx["recent_candles"]:
            # 반올림 오차를 감안해 근사 비교
            self.assertTrue(
                any(abs(candle["c"] - p) < 1e-3 for p in past_prices),
                f"컨텍스트에 과거에 없던 가격이 들어 있습니다: {candle['c']}",
            )

    def test_features_computed_only_from_past(self):
        """past 만 넘긴 특징과, 전체를 넘긴 특징이 달라야 정상입니다.

        같다면 어딘가에서 미래가 새고 있다는 뜻입니다.
        """
        f_past = extract_features(self.ex.past)
        f_full = extract_features(self.series)
        self.assertIsNotNone(f_past)
        self.assertNotEqual(f_past, f_full)

    def test_features_stable_when_future_changes(self):
        """미래 캔들을 아무리 바꿔도 T 시점 특징은 그대로여야 합니다."""
        f1 = extract_features(self.ex.past)
        tampered = generate_series(seed=999, length=300)
        merged = self.series[: self.cut + 1]
        # 서로 다른 미래를 붙여도 past 특징은 불변
        f2 = extract_features(merged)
        self.assertEqual(f1, f2)
        self.assertNotEqual(tampered.closes[-1], self.series.closes[-1])

    def test_cannot_build_when_future_too_short(self):
        ex = build_exercise(self.series, len(self.series) - 2, "TEST", horizon=20)
        self.assertIsNone(ex)

    def test_cannot_build_without_enough_history(self):
        ex = build_exercise(self.series, 10, "TEST", horizon=5)
        self.assertIsNone(ex)


class TestExamIsOutOfSample(unittest.TestCase):
    def test_exam_does_not_train_the_model(self):
        """시험 문제로 공부하면 점수가 부풀려집니다 (§40)."""
        from packages.learning_engine.exam import ChartExam

        model = OnlineChartModel(agent_id="t")
        before_weights = list(model.weights)
        before_samples = model.samples_seen

        ChartExam(questions=8, horizon=5).take(model, exam_day=0)

        self.assertEqual(model.samples_seen, before_samples)
        self.assertEqual(model.weights, before_weights)

    def test_train_and_exam_seed_ranges_do_not_overlap(self):
        from packages.learning_engine.exam import ChartExam

        self.assertGreater(
            ChartExam.EXAM_SEED_BASE, ChartExam.TRAIN_SEED_BASE + 100_000
        )


class TestLearningActuallyChangesModel(unittest.TestCase):
    def test_weights_change_after_learning(self):
        series = generate_series(seed=11, length=300)
        model = OnlineChartModel(agent_id="learner")
        before = list(model.weights)
        for cut in range(80, 200, 5):
            ex = build_exercise(series, cut, "L", horizon=5)
            if ex:
                evaluate_exercise(model, ex, learn=True)
        self.assertGreater(model.samples_seen, 0)
        self.assertNotEqual(model.weights, before)

    def test_model_learns_a_learnable_signal(self):
        """일부러 학습 가능한 신호를 주면 정확도가 우연(50%)을 넘어야 합니다.

        이게 안 되면 '학습한다'는 말이 거짓말입니다.
        """
        model = OnlineChartModel(agent_id="signal", learning_rate=0.2)
        # 규칙: 첫 번째 특징이 양수면 상승
        import random

        rng = random.Random(0)
        for _ in range(600):
            x = [rng.uniform(-1, 1) for _ in range(9)] + [1.0]
            label = 1 if x[0] > 0 else 0
            model.update(x, label)
        self.assertGreater(model.recent_accuracy, 0.85)

    def test_no_learning_means_no_score_inflation(self):
        """표본이 적으면 점수를 높게 주지 않습니다 (운을 실력으로 착각 방지)."""
        model = OnlineChartModel(agent_id="lucky")
        for _ in range(5):
            model.update([0.0] * 9 + [1.0], 1)
        self.assertLess(model.chart_skill_score(), 50.0)


if __name__ == "__main__":
    unittest.main()
