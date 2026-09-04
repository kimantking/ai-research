"""에이전트 시험 — 점수가 실제 측정 결과입니다.

두 종류
  1) ChartExam   : 학습에 쓰지 않은 구간(out-of-sample)에서 예측 정확도 측정
  2) SourceExam  : 정답이 정해진 문서들을 Research Firewall 로 판정하게 하고
                   스팸/중복/루머를 실제로 걸러내는지 측정

★ 과적합 방지 (§40)
   시험 문제는 학습에 절대 사용하지 않습니다 (learn=False).
   같은 구간에서 배우고 같은 구간에서 시험 보면 점수는 의미가 없습니다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from packages.chart_skills.series import OHLCV
from packages.chart_skills.synth import generate_series
from packages.source_validation.firewall import ResearchFirewall

from .exercise import build_exercise, evaluate_exercise
from .model import OnlineChartModel


@dataclass
class ExamResult:
    exam_type: str
    agent_id: str
    total: int
    correct: int
    score: float
    detail: dict = field(default_factory=dict)
    taken_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "exam_type": self.exam_type,
            "agent_id": self.agent_id,
            "total": self.total,
            "correct": self.correct,
            "accuracy_pct": round(self.accuracy * 100, 1),
            "score": self.score,
            "detail": self.detail,
            "taken_at": self.taken_at,
        }


# ====================================================================== 차트 시험


class ChartExam:
    """학습에 쓰지 않은 시드로 문제를 냅니다."""

    # 학습용 시드 대역과 시험용 시드 대역을 분리합니다.
    TRAIN_SEED_BASE = 1_000
    EXAM_SEED_BASE = 900_000

    def __init__(self, questions: int = 20, horizon: int = 5, length: int = 300):
        self.questions = questions
        self.horizon = horizon
        self.length = length

    def take(self, model: OnlineChartModel, exam_day: int = 0) -> ExamResult:
        rng = random.Random(self.EXAM_SEED_BASE + exam_day)
        correct = 0
        total = 0
        by_category: dict[str, int] = {}

        for q in range(self.questions):
            seed = self.EXAM_SEED_BASE + exam_day * 1000 + q
            series: OHLCV = generate_series(seed=seed, length=self.length)
            cut = rng.randint(80, self.length - self.horizon - 2)
            ex = build_exercise(series, cut, symbol=f"EXAM{q:02d}", horizon=self.horizon)
            if ex is None:
                continue
            # ★ learn=False — 시험 문제로는 절대 배우지 않습니다
            r = evaluate_exercise(model, ex, learn=False)
            if r.get("skipped"):
                continue
            total += 1
            if r["correct"]:
                correct += 1
            else:
                cat = r.get("failure_category", "UNKNOWN")
                by_category[cat] = by_category.get(cat, 0) + 1

        accuracy = correct / total if total else 0.0
        # 50% 는 동전 던지기입니다. 그걸 0점으로 봅니다.
        score = round(max(0.0, min(100.0, (accuracy - 0.5) * 200.0 + 50.0)), 1)

        return ExamResult(
            exam_type="chart_daily",
            agent_id=model.agent_id,
            total=total,
            correct=correct,
            score=score,
            detail={
                "horizon_days": self.horizon,
                "out_of_sample": True,
                "wrong_by_category": by_category,
                "note": "시험 문제는 학습에 사용하지 않았습니다 (out-of-sample).",
            },
        )


# ====================================================================== 출처 시험

_LEGIT_BODY = (
    "According to the company's 10-Q filed with the SEC on the reporting date, "
    "data center segment revenue reached $11.2 billion for the quarter. "
    "Management attributed the increase to higher shipment volumes of accelerator "
    "products. The filing also disclosed a gross margin of 74.6% and operating "
    "expenses of $3.1 billion. Guidance for the next quarter was provided in the "
    "same filing, referencing supply commitments already contracted. "
    "The figures above are taken directly from the filing."
)

_SPAM_BODY = (
    "충격! 이 종목이 다음 주 폭등 임박! 지금 사야 합니다! "
    "세력이 들어왔다는 소문이 돌고 있으며 작전주로 분류됩니다. "
    "수익률 500% 가능! 놓치면 후회합니다! 급등주 정보 무료 제공! "
    "이 기사는 보도자료를 기반으로 작성되었습니다."
)

_RUMOR_BODY = (
    "익명의 소식통에 따르면 해당 기업이 대형 계약을 앞두고 있다고 한다. "
    "업계 관계자는 익명을 전제로 계약 규모가 3조원에 달할 것이라고 전했다. "
    "다만 회사 측은 공식 입장을 내놓지 않았다. 카더라 수준의 이야기지만 "
    "시장에서는 이미 기대감이 형성되고 있다."
)

_AI_SPAM_BODY = (
    "In today's fast-paced world, investors must delve into the world of "
    "semiconductor equities. In conclusion, it is important to note that "
    "navigating the ever-changing landscape of technology investing requires "
    "careful consideration of many factors and diversification strategies."
)

_UNSOURCED_BODY = (
    "The company grew revenue 47% last quarter and now holds 62% market share "
    "in its category, with margins expanding to 38%. Analysts expect another "
    "25% increase next year and the addressable market is said to be $180 billion "
    "by the end of the decade. Growth should continue at this pace."
)


class SourceExam:
    """정답이 있는 문서로 Research Firewall 성능을 측정합니다."""

    def take(self, agent_id: str, exam_day: int = 0) -> ExamResult:
        now = datetime.now(timezone.utc)
        fw = ResearchFirewall()

        # (source_id, url, title, body, published, claims_recent, should_pass)
        cases: list[tuple[str, str, str, str, datetime | None, bool, bool]] = [
            ("s1", "https://www.sec.gov/Archives/edgar/x.htm",
             "Quarterly report", _LEGIT_BODY, now - timedelta(days=3), False, True),
            ("s2", "https://www.reuters.com/markets/a",
             "Chipmaker reports higher revenue", _LEGIT_BODY.replace("11.2", "11.3"),
             now - timedelta(days=2), False, True),
            ("s3", "https://blog.example.com/pump",
             "충격! 폭등 임박!", _SPAM_BODY, now - timedelta(days=1), False, False),
            ("s4", "https://news.example.com/rumor",
             "대형 계약설", _RUMOR_BODY, now - timedelta(days=1), False, True),
            ("s5", "https://contentfarm.example.com/ai",
             "Semiconductor investing guide", _AI_SPAM_BODY, now, False, False),
            ("s6", "https://finance.example.com/nums",
             "Company posts strong growth", _UNSOURCED_BODY, now, False, True),
            # 오래된 자료를 최신처럼 주장
            ("s7", "https://news.example.com/old",
             "BREAKING: latest results", _LEGIT_BODY.replace("11.2", "9.9"),
             now - timedelta(days=800), True, False),
            # s2 를 거의 그대로 복사한 기사 → 근사 중복으로 잡혀야 함
            ("s8", "https://aggregator.example.com/copy",
             "Chipmaker reports higher revenue",
             _LEGIT_BODY.replace("11.2", "11.3") + " Additional context follows.",
             now - timedelta(days=2), False, False),
            ("s9", "https://www.reddit.com/r/stocks/comments/x",
             "anyone else seeing this?", _RUMOR_BODY, now, False, True),
            ("s10", "https://www.fda.gov/news/x",
             "FDA approves application", _LEGIT_BODY, now - timedelta(days=5), False, True),
        ]

        correct = 0
        results = []
        confusion = {"true_pass": 0, "true_block": 0, "false_pass": 0, "false_block": 0}

        for sid, url, title, body, pub, claims_recent, should_pass in cases:
            v = fw.check(sid, url, title, body, published=pub, now=now,
                         claims_recent=claims_recent)
            ok = v.passed == should_pass
            correct += int(ok)
            if v.passed and should_pass:
                confusion["true_pass"] += 1
            elif (not v.passed) and (not should_pass):
                confusion["true_block"] += 1
            elif v.passed and not should_pass:
                confusion["false_pass"] += 1   # ★ 제일 위험한 오류
            else:
                confusion["false_block"] += 1

            results.append({
                "source_id": sid,
                "expected_pass": should_pass,
                "actual_pass": v.passed,
                "correct": ok,
                "tier": v.tier.value,
                "reasons": v.reasons,
                "penalties": v.penalties,
            })

        total = len(cases)
        # 스팸을 통과시킨 오류(false_pass)에 가중 감점 — 이게 제일 해롭기 때문
        raw = correct / total
        penalty = confusion["false_pass"] / total * 0.5
        score = round(max(0.0, min(100.0, (raw - penalty) * 100)), 1)

        return ExamResult(
            exam_type="source_verification",
            agent_id=agent_id,
            total=total,
            correct=correct,
            score=score,
            detail={
                "confusion": confusion,
                "false_source_acceptance_rate": round(confusion["false_pass"] / total, 3),
                "cases": results,
                "note": "스팸을 통과시킨 오류에는 가중 감점이 적용됩니다.",
            },
        )
