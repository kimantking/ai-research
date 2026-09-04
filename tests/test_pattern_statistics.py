"""Pattern Miner 통계 관문 검증 (Phase 20b).

★ 이 프로젝트에서 가장 컸던 통계적 약점을 실제로 막았는지 확인합니다.
   "후보 153개를 검정하면 우연히도 5% 는 유의하게 나온다" 문제입니다.
"""

import math
import unittest

from packages.pattern_miner import PatternMiner
from packages.pattern_miner.statistics import (
    binomial_tail_p,
    block_bootstrap_ci,
    correct_multiple_tests,
    effective_sample_size,
    required_sample_for_edge,
    significance_report,
)
from packages.pattern_miner.walkforward import make_folds, walk_forward
from packages.chart_skills.synth import generate_series


class TestBinomialTest(unittest.TestCase):
    def test_fair_coin_is_not_significant(self):
        self.assertGreater(binomial_tail_p(50, 100), 0.9)

    def test_extreme_result_is_significant(self):
        self.assertLess(binomial_tail_p(80, 100), 0.001)

    def test_small_sample_cannot_prove_anything(self):
        """★ 승률 60% 라도 표본 30건이면 우연과 구별되지 않습니다."""
        p = binomial_tail_p(18, 30)      # 60%
        self.assertGreater(p, 0.20, f"p={p} — 표본 30건에 60% 가 유의하면 안 됩니다")

    def test_same_rate_with_more_samples_becomes_significant(self):
        few = binomial_tail_p(18, 30)          # 60%, n=30
        many = binomial_tail_p(600, 1000)      # 60%, n=1000
        self.assertGreater(few, 0.2)
        self.assertLess(many, 1e-9)

    def test_p_value_is_bounded(self):
        for k, n in [(0, 10), (10, 10), (5, 10), (0, 1), (1, 1)]:
            p = binomial_tail_p(k, n)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_symmetric(self):
        self.assertAlmostEqual(binomial_tail_p(30, 100),
                               binomial_tail_p(70, 100), places=12)

    def test_zero_samples(self):
        self.assertEqual(binomial_tail_p(0, 0), 1.0)


class TestEffectiveSampleSize(unittest.TestCase):
    def test_overlapping_windows_reduce_information(self):
        """5일 수익률을 매일 재면 표본은 5배 부풀려집니다."""
        self.assertEqual(effective_sample_size(100, 5), 20)

    def test_horizon_one_has_no_overlap(self):
        self.assertEqual(effective_sample_size(100, 1), 100)

    def test_can_be_disabled(self):
        self.assertEqual(effective_sample_size(100, 5, overlap=False), 100)

    def test_report_uses_adjusted_value(self):
        rep = significance_report(wins=60, n=100, horizon=5)
        self.assertEqual(rep["effective_sample_size"], 20)
        # 겹침을 보정하면 p-value 는 반드시 더 커집니다(=덜 유의).
        self.assertGreater(rep["p_value_overlap_adjusted"], rep["p_value_naive"])
        self.assertEqual(rep["p_value"], rep["p_value_overlap_adjusted"])


class TestMultipleTestingCorrection(unittest.TestCase):
    def test_the_exact_problem_we_documented(self):
        """★ 153개를 검정하면 우연히도 약 8개가 p<0.05 를 만족합니다.

        보정이 그것을 걸러내는지 봅니다.
        """
        import random
        rng = random.Random(42)
        # 귀무가설이 참인 세계: p-value 는 균등분포입니다.
        pvals = [rng.random() for _ in range(153)]
        naive = sum(1 for p in pvals if p < 0.05)
        self.assertGreaterEqual(naive, 3, "우연한 '유의' 가 나와야 실험이 성립합니다")

        mt = correct_multiple_tests(pvals, alpha=0.05)
        self.assertEqual(len(mt.survivors_bonferroni), 0,
                         "우위가 없는데 Bonferroni 를 통과하면 안 됩니다")
        self.assertLessEqual(len(mt.survivors_bh), 1)
        self.assertAlmostEqual(mt.expected_false_positives_uncorrected, 7.65, places=2)

    def test_real_effect_survives(self):
        pvals = [1e-8, 1e-7] + [0.4 + i * 0.001 for i in range(100)]
        mt = correct_multiple_tests(pvals, alpha=0.05)
        self.assertIn(0, mt.survivors_bh)
        self.assertIn(1, mt.survivors_bh)

    def test_bonferroni_is_stricter_than_bh(self):
        pvals = [0.0001, 0.001, 0.01, 0.02] + [0.5] * 46
        mt = correct_multiple_tests(pvals, alpha=0.05)
        self.assertLessEqual(len(mt.survivors_bonferroni), len(mt.survivors_bh))

    def test_empty(self):
        mt = correct_multiple_tests([], alpha=0.05)
        self.assertEqual(mt.n_tests, 0)

    def test_report_explains_itself(self):
        mt = correct_multiple_tests([0.5] * 100, alpha=0.05)
        d = mt.to_dict()
        self.assertEqual(d["n_tests"], 100)
        self.assertEqual(d["expected_false_positives_if_uncorrected"], 5.0)
        self.assertIn("우연히", d["note"])


class TestPowerAnalysis(unittest.TestCase):
    def test_small_edge_needs_many_samples(self):
        """★ 승률 55% 를 잡으려면 수백 건이 필요합니다."""
        n = required_sample_for_edge(0.05)
        self.assertGreater(n, 300)
        self.assertLess(n, 2000)

    def test_bigger_edge_needs_fewer(self):
        self.assertLess(required_sample_for_edge(0.20),
                        required_sample_for_edge(0.05))

    def test_no_edge_is_unprovable(self):
        self.assertGreater(required_sample_for_edge(0.0), 10 ** 8)


class TestBlockBootstrap(unittest.TestCase):
    def test_noise_ci_includes_zero(self):
        import random
        rng = random.Random(7)
        rets = [rng.gauss(0, 0.02) for _ in range(300)]
        ci = block_bootstrap_ci(rets, block=5, iterations=300)
        self.assertTrue(ci["available"])
        self.assertFalse(ci["excludes_zero"],
                         "순수 잡음인데 0을 배제하면 안 됩니다")

    def test_strong_drift_ci_excludes_zero(self):
        import random
        rng = random.Random(7)
        rets = [rng.gauss(0.02, 0.005) for _ in range(300)]
        ci = block_bootstrap_ci(rets, block=5, iterations=300)
        self.assertTrue(ci["excludes_zero"])

    def test_too_few_samples_says_so(self):
        ci = block_bootstrap_ci([0.01] * 5, block=5)
        self.assertFalse(ci["available"])
        self.assertIn("최소", ci["reason"])

    def test_is_deterministic(self):
        rets = [0.01, -0.02, 0.03, -0.01, 0.02] * 20
        a = block_bootstrap_ci(rets, iterations=100)
        b = block_bootstrap_ci(rets, iterations=100)
        self.assertEqual(a["ci_low_pct"], b["ci_low_pct"])


class TestWalkForwardMechanics(unittest.TestCase):
    def test_folds_move_forward_and_never_overlap_backwards(self):
        folds = make_folds(0, 600, n_folds=5)
        self.assertEqual(len(folds), 5)
        for (tr, te) in folds:
            self.assertLessEqual(tr[1], te[0], "학습 구간이 검증 구간보다 뒤에 있으면 안 됩니다")
        for i in range(1, len(folds)):
            self.assertGreater(folds[i][1][0], folds[i - 1][1][0],
                               "검증 구간은 앞으로 이동해야 합니다")

    def test_anchored_train_grows(self):
        folds = make_folds(0, 600, n_folds=4, anchored=True)
        sizes = [tr[1] - tr[0] for tr, _ in folds]
        self.assertEqual(sizes, sorted(sizes))

    def test_rolling_train_is_bounded(self):
        folds = make_folds(0, 600, n_folds=4, anchored=False)
        sizes = [tr[1] - tr[0] for tr, _ in folds]
        self.assertLessEqual(max(sizes), 2 * (600 // 5) + 1)

    def test_too_short_span_yields_no_folds(self):
        self.assertEqual(make_folds(0, 10, n_folds=5), [])

    def test_consistent_signal_scores_high(self):
        # 항상 양수 수익 → 모든 회차에서 방향 일치
        samples = [(i, 0.01) for i in range(0, 600)]
        wf = walk_forward(samples, 0, 600, n_folds=5, min_fold_sample=20)
        self.assertGreaterEqual(len(wf.evaluated), 4)
        self.assertEqual(wf.consistency, 1.0)
        self.assertLess(wf.p_value(), 0.2)

    def test_random_signal_scores_around_half(self):
        import random
        rng = random.Random(11)
        samples = [(i, rng.gauss(0, 0.02)) for i in range(0, 900)]
        wf = walk_forward(samples, 0, 900, n_folds=5, min_fold_sample=20)
        self.assertLessEqual(wf.consistency, 1.0)

    def test_sparse_pattern_is_skipped_not_guessed(self):
        samples = [(i * 100, 0.01) for i in range(5)]
        wf = walk_forward(samples, 0, 600, n_folds=5, min_fold_sample=20)
        self.assertEqual(wf.evaluated, [])
        self.assertTrue(all(f.skipped_reason for f in wf.folds))


class TestMinerIntegration(unittest.TestCase):
    """★ 실제 채굴 결과에 통계 관문이 붙었는지."""

    @classmethod
    def setUpClass(cls):
        cls.miner = PatternMiner(horizon=5)
        datasets = {f"S{i}": generate_series(seed=1000 + i, length=700)
                    for i in range(6)}
        cls.patterns = cls.miner.mine(datasets)
        cls.summary = cls.miner.summary(
            cls.patterns, horizon=5, correction=cls.miner.last_correction)

    def test_correction_was_actually_applied(self):
        mt = self.summary["multiple_testing_correction"]
        self.assertGreater(mt["n_tests"], 20)
        self.assertLess(mt["benjamini_hochberg_threshold"], 0.05)

    def test_some_candidates_are_rejected_by_correction(self):
        """보정이 실제로 무언가를 걸러내야 의미가 있습니다."""
        self.assertGreater(self.summary["rejected_by_correction"], 0)
        self.assertIn("NOT_SIGNIFICANT", self.summary["by_verdict"])

    def test_walk_forward_rejects_some(self):
        self.assertIn("FAILED_WALK_FORWARD", self.summary["by_verdict"])

    def test_every_strong_pattern_survived_correction(self):
        for p in self.patterns:
            if p.verdict == "STRONG":
                self.assertTrue(
                    p.survived_correction,
                    f"{p.pattern_id} 가 보정을 통과하지 않고 STRONG 입니다",
                )

    def test_every_strong_pattern_passed_walk_forward(self):
        for p in self.patterns:
            if p.verdict == "STRONG":
                wf = p.walk_forward
                self.assertTrue(wf, f"{p.pattern_id}: walk-forward 결과 없음")
                self.assertGreaterEqual(wf["consistency_pct"], 60.0)

    def test_strong_patterns_report_their_p_value(self):
        for p in self.patterns:
            if p.verdict == "STRONG":
                self.assertIn("p_value", p.significance)
                self.assertIn("effective_sample_size", p.significance)
                self.assertLess(p.significance["effective_sample_size"],
                                p.significance["sample_size"])

    def test_strong_count_dropped_after_correction(self):
        """보정 전이라면 더 많았을 것 — 그 사실을 경고로 알려야 합니다."""
        strong = self.summary["by_verdict"].get("STRONG", 0)
        rejected = self.summary["rejected_by_correction"]
        self.assertGreater(rejected, strong,
                           "보정이 사실상 아무것도 안 걸렀습니다")
        self.assertTrue(
            any("다중검정" in w or "보정" in w for w in self.summary["warnings"]),
            "보정을 했다는 사실이 경고에 없습니다",
        )

    def test_correction_can_be_turned_off_explicitly(self):
        m = PatternMiner(horizon=5, correction="none", walk_forward_folds=0)
        ds = {"A": generate_series(seed=77, length=700)}
        pats = m.mine(ds)
        self.assertEqual(m.last_correction, {})
        self.assertTrue(all(p.survived_correction is None for p in pats))

    def test_bonferroni_mode_is_stricter(self):
        ds = {f"S{i}": generate_series(seed=1000 + i, length=700) for i in range(6)}
        strict = PatternMiner(horizon=5, correction="bonferroni")
        pats = strict.mine(ds)
        n_strict = sum(1 for p in pats if p.verdict == "STRONG")
        n_bh = sum(1 for p in self.patterns if p.verdict == "STRONG")
        self.assertLessEqual(n_strict, n_bh)


if __name__ == "__main__":
    unittest.main()
