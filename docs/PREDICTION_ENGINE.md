# PREDICTION ENGINE

구현: `packages/evaluation/`
테스트: `tests/test_evidence_and_knowledge.py`

---

## 1. Evidence Gate — 리포트 발행을 차단합니다

### 규칙

리포트 본문의 **모든 수치**는 같은 문장 안에 근거 ID `[E:xxx]` 가 있어야 합니다.

```python
gate.enforce("매출이 47% 증가했습니다.")
# → EvidenceMissing 예외. 리포트가 발행되지 않습니다.

gate.enforce("매출이 47% 증가했습니다. [E:EV001]")
# → 통과
```

### 왜 예외를 던지는가

경고 로그로 처리하면 **아무도 안 봅니다.**
리포트가 아예 안 나가야 사람이 고칩니다.

### 무엇을 숫자로 세는가

- 통화 기호가 붙은 값 (`$4.2 billion`, `₩3조`)
- 단위가 붙은 값 (`47%`, `3조원`, `2.5배`)
- **단위 없는 소수** (`182.45`) ← 실제 리포트에서 제일 위험한 종류
- 세 자리 이상 정수 (`124,300`)

숫자로 세지 **않는** 것: 근거 태그 자체, 근거 ID(`EV001`), 날짜(`2026-09-01`), 예측 ID

### 검사 단위

문장 단위입니다. 한 문장에 근거를 달았다고 다음 문장까지 통과시키지 않습니다.
다만 `"매출 47% 증가. [E:EV001]"` 처럼 근거가 마침표 뒤에 오는 경우를 위해,
**근거 태그만 있는 조각은 앞 문장에 다시 붙입니다.**

### 실제 동작 (리서치 잡)

```
EVIDENCE_GATE | 통과 — 수치 12개 전부 근거 ID 보유
```

근거를 일부러 제거하면:

```
EVIDENCE_GATE | 차단됨 — 근거 없는 수치 6건
job.status = "BLOCKED"
```

`test_evidence_gate_blocks_report_missing_citations` 가 이걸 검증합니다.

---

## 2. Prediction Journal

### 기록 항목 (§33)

```
pred_id, agent_id, ticker, ts, price_at_prediction,
direction, confidence, time_horizon_days, expected_range,
thesis, bull_case, bear_case, catalysts[], risks[], invalidation,
chart_state{}, market_regime, sector_regime, evidence_ids[], is_mock
```

`chart_state` 에 **`as_of_index`** 가 들어갑니다.
나중에 채점할 때 "예측을 내린 바로 그 시점 다음 봉부터" 계산하기 위해서입니다.
아무 구간이나 가져다 채점하면 평가 자체가 거짓말이 됩니다.

### 무엇이 기록되는가

리서치 잡의 최종 판단뿐 아니라 **차트 학습 예측도 전부** 기록됩니다.
판단은 판단입니다. 기록하지 않으면 "이 에이전트가 얼마나 맞췄나"를 물을 수 없습니다.

---

## 3. 평가 (§34)

방향만 보지 않습니다.

| 지표 | 의미 |
|---|---|
| `direction_correct` | 방향 적중 |
| `actual_return` | 실제 수익률 |
| `return_error` | 예상 범위와의 오차 |
| **`mae`** | Maximum Adverse Excursion — 최대 역행. 맞았어도 −20% 를 견뎌야 했다면 다른 얘기입니다 |
| **`mfe`** | Maximum Favorable Excursion — 최대 순행. 타이밍 평가에 씁니다 |
| `calibration_error` | 확신도와 실제 적중률의 괴리 |

### 같은 예측을 두 번 채점하지 않습니다

복기할 때마다 결과를 추가하면 성적표가 부풀려집니다.
같은 `(pred_id, horizon)` 은 **덮어씁니다.**

실측: `예측 213건 / 채점 213건` (이전 버그에서는 368건으로 부풀려졌었음)

---

## 4. Wrong Prediction Analyzer (§35)

틀렸을 때 원인을 자동 분류합니다.

| 분류 | 조건 |
|---|---|
| `OVERCONFIDENCE` | 확신도 70% 이상인데 틀림 |
| `VOLATILITY_SHOCK` | 움직임이 ATR의 3배 초과 |
| `TECHNICAL_FAILURE_FAILED_BREAKOUT` | 돌파 신호 후 하락 |
| `TECHNICAL_FAILURE_FAILED_BREAKDOWN` | 이탈 신호 후 상승 |
| `TIMING_ERROR` | 방향은 맞았는데 타이밍이 늦음 (MFE ≫ 실제) |
| `NOISE_LEVEL_MOVE` | 움직임이 ATR의 0.3배 미만 (사실상 노이즈) |
| `RANGE_WHIPSAW` | 횡보 구간에서 속임수 |
| `TREND_REVERSAL` | 추세 반전 |

실측 분포 (Technical Master, 213건):

```
TREND_REVERSAL 31, RANGE_WHIPSAW 10, FAILED_BREAKDOWN 11,
FAILED_BREAKOUT 9, VOLATILITY_SHOCK 7, TIMING_ERROR 7,
NOISE_LEVEL_MOVE 6, OVERCONFIDENCE 3
```

이 분포가 학습 메모리로 들어가고, Right Drawer 의 "최근 실수" 에 표시됩니다.

---

## 5. Agent Trust Score (§36)

```python
trust = (정확도 점수 − 캘리브레이션 벌점) × 표본 성숙도
```

- 정확도 50% = 0점 기준
- 캘리브레이션은 **구간별(ECE)** 로 계산합니다.
  예측 하나하나의 오차를 평균하면 동전던지기도 0.5가 나와서 의미가 없습니다.
- 표본 50건은 봐야 온전히 인정 (`maturity`)

실측: Technical Master — 정확도 60.6%, 캘리브 오차 0.065, **Trust 56.7**

### 어디에 쓰이는가

Investment Committee 가 **역사적으로 잘하는 에이전트의 의견에 더 큰 가중치**를 줍니다.
말을 잘하는 에이전트가 아니라, 실제로 맞춘 에이전트가 이깁니다.

---

## 6. 리서치 워크플로에서의 위치

```
Bull/Bear 독립 분석
   ↓
반대 근거 강제 탐색 (확증편향 방지)
   ↓
토론
   ↓
근거 계보 → 근거 ID 부여 (전체에서 유일)
   ↓
★ EVIDENCE GATE  ── 실패 → 리포트 발행 중단
   ↓
Evidence Judge → 투자위원회 → CIO
   ↓
★ PREDICTION JOURNAL 기록 (20일 뒤 자동 채점)
```
