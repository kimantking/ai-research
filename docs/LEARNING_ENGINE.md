# LEARNING ENGINE

> **에이전트가 실제로 공부합니다.** 진행바가 채워지는 연출이 아니라,
> 문제를 틀리면 가중치가 바뀌고 점수가 내려갑니다.

구현: `packages/learning_engine/`
테스트: `tests/test_point_in_time.py`, `tests/test_evidence_and_knowledge.py`

---

## 1. LLM 없이도 진짜 학습이 되는 이유

API 키가 없어도 학습이 돌아가야 합니다. 그래서 학습의 핵심을 **결정론적 계산**으로 만들었습니다.

각 에이전트는 자기만의 **온라인 로지스틱 회귀 모델**을 가집니다.

```
특징 10개 (RSI, MACD히스토그램, 추세, SMA교차, ROC, ATR%, RVOL, 볼린저위치, ADX, bias)
   ↓
p = sigmoid(w·x + role_prior)
   ↓
예측: UP / DOWN, 확신도 = |p − 0.5| × 2
   ↓
실제 결과 공개
   ↓
w ← w + lr × (label − p) × x − l2 × w      ← 여기서 실제로 배웁니다
```

- Bull 은 `role_prior = +0.15`, Bear 는 `−0.15` 로 출발합니다
- 서로 다른 경험을 하면 가중치가 갈라져 **실제로 다른 관점**을 갖게 됩니다
- 틀리면 교정됩니다. Bull 이 하락을 말하게 되는 경우도 생깁니다

Phase 10 에서 LLM 이 붙어도 이 모델은 사라지지 않습니다.
**LLM 이 산수를 틀리는 것을 막는 숫자 근거 제공자**로 남습니다.

---

## 2. 차트 학습 (Chart Exercise)

```
1) 과거 OHLCV 윈도우 생성
2) T 시점에서 자름     ← past = series[:T+1],  future 는 함수에 안 넘김
3) 에이전트가 1D/5D/20D 전망 작성
4) 미래 공개
5) 예측 vs 실제 비교
6) 실패 원인 분류 → 가중치 갱신
```

### Point-in-Time 이 구조로 강제됨

```python
ex = build_exercise(series, cut_index=200, symbol="NVDA", horizon=5)
ex.past      # series[:201]        ← 에이전트에게 주는 것
ex._future   # series[201:]        ← 채점 전용, agent_context() 에 절대 안 들어감
```

테스트가 검증합니다:
- `agent_context()` 안에 미래 캔들의 ts 가 단 하나도 없을 것
- 미래를 바꿔도 T 시점 특징 벡터가 변하지 않을 것

---

## 3. Effective Learning Time — 4시간의 의미

**4시간은 LLM 을 4시간 호출한다는 뜻이 아닙니다.** 커리큘럼 분량입니다.

### 학습으로 인정하는 활동

`chart_exercise`, `prediction_review`, `document_study`,
`knowledge_verify`, `contradiction_search`, `exam`, `failure_analysis`

### 학습시간에서 **제외**하는 것

`idle`, `waiting`, `duplicate_read`, `spam_filtered`,
`invalid_data`, `error_retry`, `blocked`

```python
tracker.to_dict()
# {
#   "effective_minutes": 250.0,
#   "wasted_minutes": 29.2,
#   "progress_pct": 100.0,
#   "efficiency_pct": 89.5,           ← 낮으면 시스템이 헛돌고 있다는 신호
#   "excluded_minutes": {"idle": 12.1, "spam_filtered": 9.4, "duplicate_read": 7.7}
# }
```

**같은 문서를 다시 읽으면 시간으로 안 쳐줍니다** (`content_hash` 로 판정).

### 정직성 고지

화면에 표시되는 학습시간은 **가속 시뮬레이션 값**입니다.
1 틱마다 학습 단계가 하나씩 진행되며, 실제 경과 시간과 다릅니다.
API 응답에 `time_scale: "ACCELERATED_SIMULATION"` 이 항상 포함됩니다.

---

## 4. 시험 (Exam)

### ChartExam — out-of-sample

```python
class ChartExam:
    TRAIN_SEED_BASE = 1_000
    EXAM_SEED_BASE  = 900_000      # ★ 학습 시드와 겹치지 않음
```

`evaluate_exercise(model, ex, learn=False)` — **시험 문제로는 배우지 않습니다.**
시험 문제로 공부하면 점수가 부풀려집니다. 테스트가 이걸 검증합니다.

### SourceExam

정답이 정해진 문서 10건을 Research Firewall 로 판정하게 합니다.
스팸을 통과시킨 오류(`false_pass`)에는 **가중 감점**.

---

## 5. 점수 계산 — 운을 실력으로 착각하지 않기

```python
def chart_skill_score(self):
    if self.samples_seen < 10:
        return 30.0 + self.samples_seen        # 표본 부족 → 점수 못 줌
    base = 50 + (recent_accuracy - 0.5) * 100
    penalty = calibration_error * 40
    maturity = min(1.0, samples_seen / 200)    # 200건은 봐야 온전히 인정
    return (base - penalty) * (0.6 + 0.4 * maturity)
```

### 캘리브레이션이 왜 점수에 들어가는가

**"80% 확신"이라고 말했으면 실제로 80% 맞아야 정직한 것입니다.**

확신도를 5구간으로 나눠 각 구간의 실제 적중률과 비교합니다 (ECE).
90% 확신했는데 반만 맞는 에이전트는 정확도가 높아도 점수가 깎입니다.

---

## 6. 실측값 (합성 데이터, 213문제 기준)

| 에이전트 | 표본 | 방향 정확도 | 캘리브 오차 | 차트점수 | 일일시험 |
|---|---|---|---|---|---|
| Technical Master | 213 | 60.6% | 0.065 | 59.8 | 100 |
| Semiconductor Bull | 151 | 53.0% | 0.051 | 50.5 | 50 |
| Energy Lead | 63 | 47.6% | 0.083 | 29.3 | 66.7 |

**정확도가 50~60% 근처인 것은 정상입니다.**
합성 데이터에는 예측 가능한 신호가 거의 없습니다.
시스템이 "80% 맞춥니다"라고 하지 않는 것이 오히려 정직하다는 증거입니다.

학습 기계 자체는 작동합니다 — 일부러 학습 가능한 신호를 주면 **85% 이상**을 달성합니다
(`test_model_learns_a_learnable_signal`).

---

## 7. 지식 승인

→ `docs/SOURCE_VERIFICATION.md`

---

## 8. 커리큘럼

에이전트마다 역할에 맞는 하루 루틴이 있습니다.

| 역할 | 루틴 |
|---|---|
| Sector Lead | 자료정독 → 차트학습 → 예측복기 → 자료정독 → 차트시험 → 출처시험 → 대기 |
| Bull | 차트학습 → 자료정독 → 차트학습 → 예측복기 → 차트시험 → 대기 |
| Bear | 자료정독 ×2 → 차트학습 → 차트시험 → 예측복기 → 대기 → 차트학습 |
| Technical | 차트학습 ×3 → 차트시험 → 대기 |
| Source Verification | 출처검증 ×2 → 자료정독 → 출처시험 → 대기 |
| 임원 | 예측복기 → 자료정독 ×2 → 예측복기 → 출처시험 → 대기 |

시작 단계는 에이전트 ID 해시로 어긋나게 배치합니다.
전부 같은 단계에서 시작하면 16명이 한 방에 몰려 있다가 다 같이 이동합니다.
사무실처럼 보이지도 않고, 부하도 한 순간에 몰립니다.

### LEARNING_ONLY 모드

이 모드에서는 **투자 추천을 하지 않습니다.** 자료수집·검증·공부·복기·시험만 합니다.
