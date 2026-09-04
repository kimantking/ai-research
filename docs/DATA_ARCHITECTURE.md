# DATA ARCHITECTURE

## 1. 한 문장

> **에이전트는 인터넷을 직접 읽지 않습니다.** 모든 데이터는 파이프라인을 통과해야 하고,
> 통과한 것만 "그 시점에 알 수 있었던 정보"로 저장됩니다.

---

## 2. 파이프라인

```
[SOURCE]                외부 (SEC EDGAR / 시세 / 뉴스)
   │  Provider 인터페이스 — 공급자를 갈아끼워도 위 계층은 그대로
   ▼
[COLLECTOR]             rate limit, retry, User-Agent, robots.txt
   ▼
[RAW STORAGE]           data/raw/{source}/{date}/*.json.gz  — 원본 불변 보관
   │                    content_hash 계산
   ▼
[RESEARCH FIREWALL]     ★ docs/RESEARCH_FIREWALL.md
   │  본문 추출 → 정확 중복 → 근사 중복 → 스팸 → 티커 검증 → 출처 없는 숫자
   ▼
[VALIDATION]            스키마 · 범위 · 이상치
   ▼
[NORMALIZATION]         단위 / 통화 / 타임존 (UTC 저장, 표시만 KST)
   ▼
[ENTITY RESOLUTION]     ticker → company_id (CIK 기준)
   │                    상장폐지 · 사명변경 · 티커 재사용 처리
   ▼
[SOURCE LINEAGE]        원문 추적. 독립 근거 수 ≠ 페이지 수
   ▼
[POINT-IN-TIME STORE]   ★ 4개 타임스탬프 + 버전
   ▼
[KNOWLEDGE CANDIDATE]
   ▼
[VERIFICATION]          출처 · 중복 · 모순 · 근거 검사
   ▼
[APPROVED KNOWLEDGE]  ──실패──→  [REJECTED KNOWLEDGE]  (재유입 대조용 보존)
```

---

## 3. Point-in-Time — 이 프로젝트의 심장

### 문제

일반 DB는 "지금의 진실"만 저장합니다.

기업이 2026년 3월에 2025년 실적을 **정정**하면, DB에는 정정된 값만 남습니다.
그 상태로 2025년 12월 시점을 분석하면 — 그때는 존재하지도 않았던 숫자를 보게 됩니다.
백테스트 수익률은 환상적으로 나오고, 실전에서는 전부 잃습니다.

이것이 **look-ahead bias** 입니다.

### 해결: 4개의 시간축

| 필드 | 의미 | 예 |
|---|---|---|
| `event_time` | 사건이 실제 발생한 시각 | 2026 Q2 결산 종료일 |
| `published_time` | **세상에 공개된 시각** ← 조회 필터 기준 | 10-Q가 EDGAR에 접수된 시각 |
| `received_time` | 우리가 가져온 시각 | 크롤러 fetch 시각 |
| `effective_time` | 이 값이 유효한 것으로 간주되는 시각 | 정정 시 새 버전 |

### 조회는 반드시 as_of 를 통해서만

```python
# packages/pit_store/store.py
store.get_fact("AAPL:2025Q4:revenue", as_of=T)
#   → published_time <= T 인 것 중 가장 최신 버전
#   → T 이후 공개된 값은 조회 통로 자체가 없습니다
```

`PITSeriesView` 는 슬라이싱해도 미래로 넘어갈 수 없습니다.
`view[1000]` 처럼 범위를 벗어나면 IndexError 를 던집니다.

### 정정은 덮어쓰지 않고 새 버전

| id | fact_key | value | published_time | version | supersedes |
|---|---|---|---|---|---|
| 1 | AAPL:2025Q4:revenue | 124.3B | 2026-01-30 | 1 | null |
| 2 | AAPL:2025Q4:revenue | 124.1B | 2026-03-15 | 2 | 1 |

- `as_of = 2026-02-01` → **124.3B** (당시의 진실)
- `as_of = 2026-04-01` → **124.1B**

**과거 분석이 미래에도 그대로 재현됩니다.** 감사(Audit)의 전제 조건입니다.

### 데이터 자체의 무결성도 검사

`published_time < event_time` 인 레코드는 저장 시점에 거부합니다.
사건보다 먼저 공개될 수는 없기 때문입니다. 그런 데이터는 오류입니다.

---

## 4. 저장 필드 (최소)

```
ticker, company_id, company_name, sector, industry,
source_id, source_url, source_type, source_tier, source_domain,
original_source_id, content_hash,
event_time, published_time, received_time, ingested_time, effective_time,
confidence, verification_status, version, raw_reference
```

---

## 5. 데이터베이스 스키마 (Phase 5에서 구현)

```sql
companies(company_id PK, cik, name, sector, industry)
tickers(ticker, company_id FK, exchange, valid_from, valid_to)   -- 티커 재사용 대응

sources(source_id PK, url, domain, source_type, tier, fetched_at,
        content_hash, original_source_id FK NULL, is_independent)
claims(claim_id PK, subject, statement, verification_status, created_at)
evidence(evidence_id PK, claim_id FK, source_id FK, excerpt, confidence)

facts(fact_id PK, company_id FK, fact_key, value_num, value_text, unit,
      event_time, published_time, received_time, effective_time,
      version, supersedes FK NULL, source_id FK, confidence)
      -- INDEX (company_id, fact_key, published_time DESC)

bars(company_id FK, tf, ts, o,h,l,c,v, provider, received_time)
     -- PK (company_id, tf, ts)

knowledge(k_id PK, agent_id, namespace, statement, embedding vector(N),
          status, evidence_ids[], created_at, version)
knowledge_rejected(k_id PK, statement, reason, evidence_ids[], created_at)

predictions(...)   -- docs/PREDICTION_ENGINE.md
audit_log(...)     -- 재현성을 위한 전체 기록
llm_usage(...)     -- docs/COST_CONTROL.md
```

---

## 6. 현재 구현 상태

| 계층 | 상태 |
|---|---|
| Provider 인터페이스 | 설계 완료, MOCK 구현체 동작 중 |
| RAW STORAGE | Phase 11 |
| Research Firewall | ✅ **동작 + 테스트** |
| Source Lineage | ✅ **동작 + 테스트** |
| Point-in-Time Store | ✅ **동작 + 테스트** (메모리 기반, Phase 5에서 DB로) |
| Entity Resolution | Phase 11 |
| Knowledge 승인 | ✅ **동작 + 테스트** |
| PostgreSQL 영속화 | Phase 5 |

---

## 7. 왜 DuckDB / Parquet 을 나중에 고려하는가

시계열은 양이 많고 분석 쿼리 위주입니다. PostgreSQL 하나로 다 하면
`WHERE published_time <= T` 스캔이 무거워집니다.

- **PostgreSQL** — 에이전트 상태, 지식, 감사 로그 (트랜잭션 필요)
- **DuckDB + Parquet** — 대용량 OHLCV, 팩터 (분석 쿼리)

다만 **MVP에서는 넣지 않습니다.** 데이터가 실제로 커진 다음에 도입합니다.
