# COST CONTROL

---

## 1. 현재 비용: $0

LLM 이 연결되어 있지 않습니다. 그런데도 다음이 전부 동작합니다.

- 에이전트 학습 (차트 문제 풀이 + 가중치 갱신)
- 시험 (차트 / 출처 검증)
- Research Firewall (스팸·중복·루머 판정)
- 지식 승인 파이프라인
- 예측 저널 + 채점 + 실패 원인 분류
- 백테스트
- Pattern Miner

**이것들은 전부 결정론적 계산이라 LLM 이 필요 없습니다.**
LLM 은 "심층 추론"에만 씁니다 → `docs/MODEL_ROUTING.md`

`/api/system/health` 응답:
```json
"llm_calls": 0,
"llm_cost_usd": 0.0,
"llm_note": "LLM 미연결 상태입니다. 학습과 검증은 로컬 계산으로 동작 중입니다."
```

---

## 2. 비용 폭발을 막는 장치 (지금 켜져 있음)

| 장치 | 구현 | 검증 |
|---|---|---|
| **Router 상한 8명** | `Router.max_agents` | `test_selects_only_a_few` |
| **일괄 깨우기 차단** | `wake_count_guard()` — 초과 시 예외 | `test_guard_blocks_mass_wakeup` |
| **REGISTERED 는 실행 안 됨** | 177명 중 16명만 ACTIVE | `test_registered_agents_never_run` |
| **중복 문서 재독 차단** | `content_hash` 기반 | `EffectiveTimeTracker` |
| **스팸 조기 차단** | Research Firewall 이 LLM 전에 거름 | 25개 테스트 |
| **패턴 탐색 결과 캐시** | `_pattern_cache` | — |

### 왜 Router 상한이 중요한가

실수로 `select_for_research()` 가 177명을 반환하면
한 번의 리서치에 **API 호출이 20배** 늘어납니다.
`wake_count_guard()` 가 예외를 던져 그 일이 일어나지 않게 합니다.

---

## 3. 비용 추적 (Phase 10에서 활성화)

```sql
llm_usage(
  id, agent_id, job_id, provider, model,
  prompt_tokens, completion_tokens, cost_usd, ts
)
```

집계 단위: 에이전트별 / 작업별 / 일별

UI 상단 바에 **오늘 예상 비용**이 항상 표시됩니다 (지금은 $0).

---

## 4. 예산 한도

```yaml
# config/models.yaml
budget:
  daily_usd_limit: 5.0
  on_exceed: pause_and_queue
  warn_at_pct: 80
```

`.env` 의 `DAILY_LLM_BUDGET_USD` 로도 조정합니다.

**한도 초과 시 조용히 실패하지 않습니다.** 작업을 큐에 남기고 멈춘 뒤,
UI 에 "예산 한도로 중단됨" 을 표시합니다.

---

## 5. 데이터 비용

유료 API 는 **사용자 승인 없이 가입하지 않습니다.**

무료·공식 소스를 먼저 씁니다:

| 소스 | 비용 | 재배포 |
|---|---|---|
| SEC EDGAR | 무료 | ✅ 자유 |
| FRED | 무료 (키 필요) | 확인 필요 |
| FDA openFDA | 무료 | ✅ 예상 |
| ClinicalTrials.gov | 무료 | ✅ 예상 |
| yfinance | 무료 | ❌ 개인 연구용만 |

유료 provider 도입 전 확인 항목:
무료 대안 존재 여부 / 공식 API 여부 / Rate Limit / 라이선스 / 재배포 제한

---

## 6. 비용 절감 설계 요약

```
비싼 것:  LLM 호출
싼 것:    파이썬 계산

→ 계산으로 할 수 있는 건 전부 계산으로 한다
→ LLM 은 "사람이 봐도 어려운 판단"에만 쓴다
→ 안 쓰는 에이전트는 자고 있다
→ 같은 문서를 두 번 읽지 않는다
→ 스팸은 LLM 에 도달하기 전에 걸러진다
```
