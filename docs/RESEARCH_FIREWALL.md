# RESEARCH FIREWALL

> 검색 결과를 에이전트에게 **그대로 넘기지 않습니다.**

구현: `packages/source_validation/`
테스트: `tests/test_research_firewall.py` (25개)

---

## 1. 왜 필요한가

LLM에게 웹 검색 결과를 그대로 주면 다음이 벌어집니다.

- 펌핑 글을 근거로 씁니다
- 로이터 기사 하나를 복사한 50개 사이트를 "50개 출처가 확인했다"고 셉니다
- 2년 전 기사를 최신 뉴스로 인용합니다
- 출처 없는 숫자를 사실처럼 리포트에 넣습니다

이건 프롬프트로 "조심하세요"라고 말해서 해결되지 않습니다. **필터가 필요합니다.**

---

## 2. 탐지 항목과 처리

| 탐지 | 방법 | 처리 |
|---|---|---|
| **정확 중복** | `content_hash` (정규화 후 SHA-256) | 차단 |
| **근사 중복 (신디케이션)** | **SimHash 64bit, 해밍거리 ≤ 8** | 차단 + 원문 기록 |
| 펌핑/낚시 | 패턴 매칭 (한/영) | 신뢰도 × 0.35 |
| 광고/보도자료 | 패턴 매칭 | 차단 |
| AI 생성 스팸 | 정형 문구 패턴 | 차단 |
| 익명 루머 | 패턴 매칭 | 신뢰도 × 0.4, **확정 사실 자격 박탈** |
| 오래된 정보를 최신처럼 | `published_time` + `claims_recent` | 차단 |
| 발행일 불명 | 메타데이터 없음 | 신뢰도 × 0.7 |
| **출처 없는 숫자** | 숫자 패턴 + 출처 표현 패턴 | 신뢰도 × 0.4, **확정 사실 자격 박탈** |
| 본문 과소 (콘텐츠 팜) | 40단어 미만 | 신뢰도 × 0.5 |

### 설계 원칙: 애매하면 버리지 않고 신뢰도를 낮춘다

확실히 차단해야 하는 것만 차단하고, 나머지는 통과시키되 confidence 를 깎습니다.
**무엇이든 확신하는 필터가 제일 위험합니다.**

---

## 3. SimHash — 왜 정확 해시로는 부족한가

로이터 기사를 50개 사이트가 옮깁니다. 각 사이트는 문단 하나씩 다릅니다.

```
원문:   "According to the 10-Q filed with the SEC, revenue was $4.2 billion..."
복사본: "According to the 10-Q filed with the SEC, revenue was $4.2 billion...
         Additional context was provided by the aggregator site."
```

- `content_hash` → **다름** (못 잡음)
- `simhash` 해밍거리 → **≤ 8** (잡힘)

SimHash 는 내용이 비슷하면 해시도 비슷해지는 성질을 이용합니다.
단어 3개씩 묶은 shingle 로 계산하므로 문장 순서까지 반영됩니다.

```python
from packages.source_validation.simhash import simhash, is_near_duplicate
is_near_duplicate(simhash(a), simhash(b))   # True
```

---

## 4. Source Lineage — 독립 근거 세기

```
50개 사이트가 로이터 기사 1건을 복사

page_count                    = 51
independent_evidence_count    = 1     ← 신뢰도 계산에 쓰는 값
```

```python
tracker.verdict()
# {
#   "status": "SINGLE_SOURCE",
#   "page_count": 51,
#   "independent_evidence_count": 1,
#   "note": "복사 기사 50건은 독립 근거 1건입니다"
# }
```

### 판정

| status | 조건 | 의미 |
|---|---|---|
| `CONFIRMED_FACT` | 확정 자격 있는 등급의 **독립** 출처 2건 이상 | 사실로 인정 |
| `SINGLE_SOURCE` | 독립 출처 1건 | 추가 검증 필요 |
| `DISCOVERY_LEAD` | 낮은 등급만 있음 | **버리지 않음.** 조사 시작점 |
| `NO_EVIDENCE` | 아무것도 없음 | 주장 금지 |

---

## 5. Source Tier

`config/source_tiers/default.yaml` 에서 바꿉니다. 코드에 하드코딩하지 않습니다.

| Tier | 가중치 | 확정 사실 자격 | 예 |
|---|---|---|---|
| **S** | 1.00 | ✅ | SEC, FDA, 거래소, DART, 정부 |
| **A** | 0.80 | ✅ | Reuters, Bloomberg, WSJ, 공식 IR |
| **B** | 0.60 | ✅ | SemiAnalysis, FierceBiotech 등 전문매체 |
| **C** | 0.40 | ❌ | 애널리스트 코멘터리 |
| **D** | 0.20 | ❌ | 블로그, Substack |
| **E** | 0.05 | ❌ | Reddit, X, StockTwits |

### Tier E 를 버리지 않는 이유

레딧 소문이 **틀렸다는 뜻이 아닙니다.** "아직 확인되지 않았다"는 뜻입니다.

실제로 중요한 정보가 커뮤니티에서 먼저 도는 경우가 많습니다.
그래서 `DISCOVERY_LEAD` 로 남겨 조사 대상에 넣되,
고품질 독립 출처가 확인해주기 전까지는 절대 확정 사실이 되지 못하게 합니다.

---

## 6. 실제 동작 예 (SourceExam 에서)

에이전트는 매일 이 시험을 봅니다. 정답이 정해진 문서 10건을 판정합니다.

| 케이스 | 통과해야 하나 | 이유 |
|---|---|---|
| SEC 10-Q | ✅ | Tier S, 출처 명시 |
| Reuters 기사 | ✅ | Tier A |
| 펌핑 글 ("충격! 폭등 임박! 500% 가능!") | ❌ | 낚시 + 보도자료 |
| 익명 소식통 계약설 | ✅ 통과하되 확정 자격 없음 | 조사 단서로는 가치 있음 |
| AI 생성 스팸 | ❌ | 정형 문구 |
| 출처 없는 숫자 나열 | ✅ 통과하되 확정 자격 없음 | 참고만 |
| 2년 전 기사를 "BREAKING: latest" 로 | ❌ | 시점 위장 |
| Reuters 기사 복사본 | ❌ | 근사 중복 |
| Reddit 글 | ✅ 통과하되 Tier E | Discovery Lead |
| FDA 발표 | ✅ | Tier S |

**채점 시 "스팸을 통과시킨 오류(false_pass)"에는 가중 감점**을 합니다.
정상 문서를 실수로 막는 것보다, 스팸을 통과시키는 게 훨씬 해롭기 때문입니다.

현재 담당 에이전트 점수: **90/100** (실측)

---

## 7. 저작권 관련 제약

- 기사 **전문을 DB에 영구 저장하지 않습니다.**
- 저장하는 것: URL, 제목, 발행일, 원문 소스, **추출된 사실 + 짧은 인용**, content_hash
- `robots.txt` 를 존중합니다

우리가 원하는 건 기사가 아니라 **검증된 사실**입니다.

---

## 8. Phase 13 에서 추가할 것

| 항목 | 도구 | 라이선스 |
|---|---|---|
| 본문 추출 + canonical URL + 발행일 | `trafilatura` | Apache-2.0 |
| MinHash LSH (대규모 근사 중복) | `datasketch` | MIT |
| 렌더링 필요한 페이지 | `Playwright` | Apache-2.0 |

지금은 SimHash 자체 구현으로 충분합니다 (의존성 0).
