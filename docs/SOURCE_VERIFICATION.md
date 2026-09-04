# SOURCE VERIFICATION

> Research Firewall 이 "이 문서를 읽을 가치가 있나"를 판정한다면,
> Source Verification 은 "이 주장을 사실로 인정할 수 있나"를 판정합니다.

구현: `packages/source_validation/lineage.py`, `packages/learning_engine/knowledge.py`

---

## 1. NO EVIDENCE POLICY

모든 에이전트 공통 규칙입니다.

| 상황 | 처리 |
|---|---|
| **NO EVIDENCE** | 주장 자체를 금지 |
| **WEAK EVIDENCE** (Tier C~E 만) | `confidence: LOW` + UI 경고 |
| **CONFLICTING EVIDENCE** | 결론 내지 않고 **추가 리서치 큐에 투입** |
| **UNKNOWN** | "모른다"고 명시. 이게 정답인 경우가 많습니다 |

이건 프롬프트 지시가 아니라 **코드가 강제**합니다 → `docs/PREDICTION_ENGINE.md` 의 Evidence Gate.

---

## 2. 지식 승인 파이프라인

```
KnowledgeCandidate
   │
   ├─ 0) 과거에 기각된 주장인가?          → 재유입이면 즉시 기각 + 횟수 기록
   ├─ 1) 출처가 하나라도 있나?             → 없으면 기각
   ├─ 2) 계보 분석 (독립 근거 수)          → docs/RESEARCH_FIREWALL.md
   ├─ 3) 이미 아는 지식과 중복인가?        → SimHash 비교
   ├─ 4) 수치가 있는데 확정 자격 출처가 없나? → 기각
   └─ 5) 최종 판정
          ├─ CONFIRMED_FACT        → APPROVED
          ├─ SINGLE_SOURCE         → NEEDS_MORE_RESEARCH (폐기 안 함)
          ├─ DISCOVERY_LEAD        → NEEDS_MORE_RESEARCH
          └─ NO_EVIDENCE           → REJECTED
```

---

## 3. 기각된 지식을 왜 보관하는가

같은 거짓 정보는 **반복해서 들어옵니다.**

```python
store.submit(KnowledgeCandidate("근거 없는 주장", "agent1", sources=[]))
# → REJECTED

store.submit(KnowledgeCandidate("근거 없는 주장", "agent2", sources=[]))
# → REJECTED
#   checks.previously_rejected = {"times_seen": 2, "original_reasons": [...]}
```

`times_seen` 이 올라가는 주장은 **조직적으로 퍼뜨려지고 있다는 신호**입니다.
Audit 화면에서 "재유입 N건" 으로 확인할 수 있습니다.

기각 판정은 SimHash 로 비교하므로, 문구를 조금 바꿔서 다시 넣어도 잡힙니다.

---

## 4. 승인 조건

```yaml
# config/source_tiers/default.yaml
confirmed_fact_requires:
  min_independent_sources: 2      # ★ 페이지 수가 아니라 '독립 원문' 수
  min_tier: B
  contradiction_check: required
```

숫자가 포함된 주장은 더 엄격합니다.
Tier C 이하 출처만 있으면 **수치 주장은 무조건 기각**합니다.
블로그가 인용한 매출액을 사실로 저장하면, 그 순간 시스템 전체가 오염됩니다.

---

## 5. Evidence Graph

최종 주장은 원문까지 추적 가능해야 합니다.

```
CLAIM  "NVDA 데이터센터 매출이 전년 대비 X% 증가"
  │
  ├─ EVIDENCE EV001 ─ SOURCE(10-Q) ────── ORIGINAL: SEC        [Tier S] ✅ 독립
  ├─ EVIDENCE EV002 ─ SOURCE(어닝콜) ──── ORIGINAL: 회사 IR    [Tier A] ✅ 독립
  └─ EVIDENCE EV003 ─ SOURCE(기사) ────── ORIGINAL: 위 10-Q    [Tier A] ❌ 독립 아님

독립 근거 = 2건  →  CONFIRMED_FACT
```

UI 의 Research 화면에서 각 논거 옆에 `EV001` 배지가 붙습니다.
Audit 화면에서 승인/기각 내역을 전부 볼 수 있습니다.

---

## 6. 담당 에이전트

| 에이전트 | 역할 |
|---|---|
| `source_verification` | Research Firewall 운영, 중복·신디케이션 탐지 |
| `data_quality` | 스키마 검증, 이상치, 시점 무결성 |
| `evidence_judge` | 근거 없는 숫자 차단, 주장→근거 추적 |
| `red_team` | 가정 공격, 반대 근거 강제 탐색 |

이 넷은 **섹터와 무관하게 모든 리서치에 참여**합니다 (`Router.ALWAYS_ON_ROLES`).
