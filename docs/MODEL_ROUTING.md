# MODEL ROUTING

설정: `config/models.yaml`

---

## 1. 특정 AI 회사에 종속시키지 않습니다

에이전트 프로필(177개)에는 **실제 모델명을 절대 쓰지 않습니다.**

```yaml
# config/agents/semiconductor_department.yaml
model_policy:
  default: tier_strong        # ← 등급만
  cheap_tasks: tier_cheap
```

실제 매핑은 `config/models.yaml` **한 곳**에서만 합니다.

```yaml
active_provider: none      # none | anthropic | openai | google | local
providers:
  anthropic:  {tier_strong: "", tier_mid: "", tier_cheap: ""}
  openai:     {tier_strong: "", tier_mid: "", tier_cheap: ""}
  google:     {tier_strong: "", tier_mid: "", tier_cheap: ""}
  local:      {tier_strong: "", tier_mid: "", tier_cheap: ""}
```

공급자를 통째로 바꿔도 **에이전트 설정을 하나도 안 건드립니다.**

`test_no_real_model_name_in_profiles` 가 프로필에 실제 모델명이 들어가는 것을 막습니다.

---

## 2. 작업별 라우팅

고성능 모델을 모든 일에 쓰지 않습니다.

### LLM 을 아예 쓰지 않는 작업 (코드가 처리)

| 작업 | 이유 |
|---|---|
| HTML 파싱 / 본문 추출 | LLM 불필요 |
| 중복 판정 | **결정론적이어야 함.** 같은 입력에 같은 답이 나와야 합니다 |
| 지표 계산 | **LLM 은 산수를 틀립니다** |
| 데이터 검증 | 재현성 필요 |
| Point-in-Time 쿼리 | 안전장치는 코드여야 합니다 |
| 차트 문제 채점 | 결정론적 |

### 싼 모델 (`tier_cheap`)
뉴스 분류, 엔티티 태깅, 짧은 요약

### 중간 (`tier_mid`)
문서 요약, 섹터 브리핑

### 비싼 모델 (`tier_strong`) — 여기가 실제로 가치 있는 지점
논지 합성, Bull/Bear 토론, 모순 분석, 실패 원인 분석, 최종 리포트

---

## 3. "100명 × 4시간 = 400시간 API 호출" 이 되지 않는 이유

1. **4시간은 커리큘럼 분량**이지 LLM 통화 시간이 아닙니다
2. 커리큘럼의 대부분(문서 파싱·중복 제거·지표 계산·과거 계산)은 **코드가 처리**합니다
3. **SLEEPING/REGISTERED 에이전트는 호출되지 않습니다** (177명 중 16명만 ACTIVE)
4. Router 가 한 작업에서 **최대 8명**만 깨웁니다
5. Effective Learning Time 에서 idle·중복·스팸·에러 루프는 제외됩니다

현재 상태에서 **LLM 호출 0회, 비용 $0** 로 학습·검증·백테스트·패턴탐색이 전부 돌아갑니다.

---

## 4. 도입 예정: LiteLLM

Phase 10 에서 `BerriAI/litellm` (MIT, ⭐53.8k) 을 씁니다.

- 100개 이상 공급자를 OpenAI 포맷으로 통일
- 비용 추적, 예산 한도, 로드밸런싱 내장

**단, 우리 코드는 LiteLLM 에도 직접 묶이지 않습니다.**

```
packages/llm_gateway/
├─ interface.py     ← 우리 인터페이스 (얇은 층)
├─ litellm_impl.py  ← 구현체
├─ router.py        ← 작업 난이도 → 모델 등급
└─ cost.py          ← agent_id / job_id 별 기록
```

"특정 LLM 에 종속되지 않는다"가 목표인데 LiteLLM 자체에 종속되면 같은 문제입니다.

---

## 5. 예산 초과 시 동작

```yaml
budget:
  daily_usd_limit: 5.0
  on_exceed: pause_and_queue     # 조용히 실패하지 않습니다
  warn_at_pct: 80
```

한도를 넘으면 **작업을 큐에 남기고 멈춥니다.**
조용히 실패하면 사용자는 시스템이 도는 줄 알고 있다가 나중에 빈 결과를 받게 됩니다.
