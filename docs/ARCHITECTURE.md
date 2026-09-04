# ARCHITECTURE — AI STOCK RESEARCH OFFICE

- 작성일: 2026-09-02
- 상태: **Phase 3 초안** (Phase 4 스캐폴드 착수 전 사용자 승인 대기)
- 전제: Windows 11 + PowerShell, 프로젝트 루트 `C:\ai-research`, 완전 격리

---

## 0. 이 시스템을 한 문장으로

> **"근거 없는 주장을 물리적으로 만들 수 없게 만든 AI 리서치 조직, 그리고 그 조직이 지금 뭘 하고 있는지 보여주는 픽셀 사무실."**

핵심은 에이전트 수가 아니라 **세 가지 강제 장치**입니다:

1. **Point-in-Time 강제** — 과거 분석 시 미래 정보 접근이 코드 레벨에서 불가능
2. **Evidence 강제** — Evidence ID 없는 숫자는 최종 리포트에 들어갈 수 없음
3. **반대편 강제** — Bull이 나오면 Bear 검색이 자동 생성됨

이 세 가지가 없으면 이 프로젝트는 그냥 "LLM이 주식 얘기 많이 하는 앱"이 됩니다.

---

## 1. 시스템 전체 구성

```
┌──────────────────────────────────────────────────────────────┐
│  BROWSER  (localhost)                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  apps/web  —  Next.js 15 (App Router) + TypeScript      │  │
│  │  ┌──────────────┐  ┌───────────────────────────────┐   │  │
│  │  │ Pixel Office │  │ Research / Agents / Learning  │   │  │
│  │  │ (Canvas 2D)  │  │ Markets / Data / Audit        │   │  │
│  │  └──────┬───────┘  └───────────────┬───────────────┘   │  │
│  └─────────┼──────────────────────────┼───────────────────┘  │
└────────────┼──────────────────────────┼──────────────────────┘
             │ WebSocket (agent events) │ REST (queries)
┌────────────▼──────────────────────────▼──────────────────────┐
│  services/api  —  FastAPI (Python 3.12)                      │
│  ┌────────────┬─────────────┬──────────────┬──────────────┐  │
│  │ REST API   │ WS Hub      │ Auth(local)  │ Health       │  │
│  └────────────┴─────────────┴──────────────┴──────────────┘  │
└───────┬──────────────────────────────────────────┬───────────┘
        │ enqueue                                  │ read
┌───────▼──────────────────┐          ┌────────────▼───────────┐
│ services/agent_runtime   │          │  DATA LAYER            │
│  LangGraph workflows     │          │  ┌──────────────────┐  │
│  ┌────────────────────┐  │          │  │ PostgreSQL 16    │  │
│  │ Research Graph     │  │◄────────►│  │  + pgvector      │  │
│  │ Debate Graph       │  │          │  └──────────────────┘  │
│  │ Learning Graph     │  │          │  ┌──────────────────┐  │
│  │ Evaluation Graph   │  │          │  │ Redis / Valkey   │  │
│  └────────────────────┘  │          │  │ (queue + pubsub) │  │
│  ┌────────────────────┐  │          │  └──────────────────┘  │
│  │ packages/*  skills │  │          │  ┌──────────────────┐  │
│  └────────────────────┘  │          │  │ data/ (parquet)  │  │
└───────┬──────────────────┘          │  │ Phase 11~        │  │
        │                             │  └──────────────────┘  │
┌───────▼──────────────────┐          └────────────────────────┘
│ services/data_worker     │
│  Providers → Firewall    │─────► 외부: SEC EDGAR / OHLCV / News
│  → Validation → PIT DB   │
└──────────────────────────┘
┌──────────────────────────┐
│ services/scheduler       │  cron-like: 일일 학습, 예측 평가(1D/5D/20D/60D)
└──────────────────────────┘
```

### 1-1. 프로세스 수와 포트

MVP에서 실제로 뜨는 것은 **5개 컨테이너 + 1개 로컬 프로세스**입니다. 그 이상 늘리지 않습니다.

| 서비스 | 컨테이너명 (compose project: `ai-stock-research-office`) | 기본 포트 | 충돌 시 |
|---|---|---|---|
| PostgreSQL + pgvector | `airo-postgres` | **5433** | 5434 → 5435 |
| Redis (또는 Valkey) | `airo-redis` | **6380** | 6381 → 6382 |
| FastAPI | `airo-api` | **8010** | 8011 → 8012 |
| Agent Runtime worker | `airo-agent-runtime` | (없음) | — |
| Scheduler | `airo-scheduler` | (없음) | — |
| Next.js (개발 중엔 로컬 실행) | — | **3010** | 3011 → 3012 |

> **포트 결정 근거**: 5432/6379/8000/3000은 다른 프로젝트가 쓸 확률이 매우 높습니다.
> **처음부터 비켜갑니다.** `audit.ps1`이 실제 사용 현황을 확인하고, `.env`에서 조정합니다.
> **다른 프로젝트를 절대 종료시키지 않습니다.**

Docker volume 이름도 전부 접두사를 붙입니다: `airo_pgdata`, `airo_redisdata`.

---

## 2. 디렉터리 구조 (실제로 만들 것만)

§10의 전체 구조 중 **MVP에 필요한 것만** 만듭니다. 나머지는 "만들 자리는 정해두되 비워둡니다".

```
C:\ai-research\
├─ .venv\                        # 프로젝트 전용 Python 3.12 (다른 프로젝트와 무관)
├─ .env                          # git 제외
├─ .env.example                  # git 포함
├─ .gitignore
├─ pyproject.toml                # Python 의존성 (uv 또는 pip)
├─ README.md
├─ THIRD_PARTY_LICENSES.md
├─ docker-compose.yml            # project name: ai-stock-research-office
│
├─ apps\
│   └─ web\                      # Next.js + TypeScript
│       ├─ package.json          # 로컬 설치만. 전역 npm 패키지 안 씀
│       └─ src\
│           ├─ app\              # office / research / agents / learning /
│           │                    # markets / data / backtest / audit / settings
│           ├─ components\
│           ├─ office\           # ★ Pixel Office 렌더러 (Canvas 2D)
│           │   ├─ OfficeRenderer.ts      # 인터페이스 (나중에 PixiJS로 교체 가능)
│           │   ├─ Canvas2DRenderer.ts
│           │   ├─ sprites\
│           │   └─ layout\       # 부서 배치 좌표
│           └─ lib\
│               └─ ws.ts         # WebSocket 클라이언트
│
├─ services\
│   ├─ api\                      # FastAPI — REST + WebSocket
│   ├─ agent_runtime\            # LangGraph 워크플로 실행
│   ├─ scheduler\                # 주기 작업
│   └─ data_worker\              # 수집 → 검증 → 정규화 → PIT 저장
│
├─ packages\                     # ★ MVP에서 실제로 만드는 것
│   ├─ shared\                   # 공통 타입/스키마/설정/로깅
│   ├─ agent_registry\           # Agent Profile 로딩·라우팅·wake-up
│   ├─ llm_gateway\              # LiteLLM 래핑 + 모델 라우팅 + 비용 기록
│   ├─ data_connectors\          # Provider 인터페이스 + 구현체
│   ├─ pit_store\                # ★ Point-in-Time 저장/조회 (핵심)
│   ├─ source_validation\        # Research Firewall
│   ├─ chart_skills\             # 지표 계산 + 멀티 타임프레임 + 차트 이미지
│   ├─ research_skills\          # 리서치 프롬프트/절차
│   ├─ evaluation\               # 예측 저널 + 평가 + 오답 분석
│   ├─ learning_engine\          # 학습 커리큘럼 + 시험
│   └─ backtest_engine\          # (Phase 19에 생성. 지금은 안 만듦)
│
├─ config\
│   ├─ agents\                   # YAML: 에이전트 프로필 (100+ 정의 가능)
│   ├─ sectors\                  # YAML: 섹터 정의
│   ├─ data_sources\             # YAML: 소스 정의
│   ├─ source_tiers\             # YAML: Tier S~E 규칙 (configurable)
│   └─ learning\                 # YAML: 커리큘럼
│
├─ data\                         # git 제외 (원본 스냅샷/parquet)
├─ logs\                         # git 제외
├─ docs\
├─ infra\
├─ tests\
└─ scripts\                      # setup.ps1 / start.ps1 / stop.ps1 / health.ps1 /
                                 # reset-local.ps1 / audit.ps1 / license-check.ps1
```

**만들지 않는 것 (그리고 이유):**
- `packages\backtest_engine` — Phase 19까지 불필요. 빈 폴더는 혼란만 준다.
- `services\learning_worker` — MVP에서는 `scheduler`가 학습 잡도 큐에 넣으면 `agent_runtime`이 처리하면 된다. 프로세스를 하나 더 띄울 이유가 없다.
- 마이크로서비스 분리 — MVP는 **모노레포 + 소수 프로세스**. 나중에 부하가 생기면 그때 쪼갠다.

---

## 3. ★ Point-in-Time 데이터 모델 (이 프로젝트의 심장)

### 3-1. 문제

일반적인 DB는 "지금의 진실"만 저장합니다. 백테스트에서 이건 재앙입니다:
- 기업이 2026년 3월에 2025년 실적을 **정정**했다 → DB에는 정정된 값만 남는다
- 2025년 12월 시점 분석에서 그 정정값을 보면 → **미래를 본 것이다 (look-ahead bias)**
- 결과: 백테스트 수익률이 환상적으로 나오고, 실전에서 다 잃는다

### 3-2. 해결: 4개의 시간축을 분리 저장

모든 데이터 레코드는 **최소 4개의 타임스탬프**를 가집니다.

| 필드 | 의미 | 예시 |
|---|---|---|
| `event_time` | 사건이 실제로 발생한 시각 | 2026 Q2 결산 종료일 |
| `published_time` | 세상에 **공개된** 시각 | 10-Q가 EDGAR에 접수된 시각 |
| `received_time` | 우리가 **가져온** 시각 | 우리 크롤러가 fetch한 시각 |
| `effective_time` | 이 값이 **유효한 것으로 간주되는** 시각 | 정정 시 새 버전이 생김 |

**핵심 규칙 (코드로 강제):**

```python
# packages/pit_store/query.py — 개념 코드
class PITQuery:
    def __init__(self, as_of: datetime):
        # as_of 이후에 공개된 정보는 물리적으로 조회 불가
        self._as_of = as_of

    def get(self, table, **filters):
        return db.query(table).filter(
            table.published_time <= self._as_of,   # ← 이 줄이 전부다
            **filters
        ).order_by(table.version.desc()).first()
```

**중요**: 에이전트는 DB에 **직접 접근하지 못합니다.** 반드시 `PITQuery`를 통해서만 접근합니다.
`as_of`는 워크플로 시작 시 주입되며, 에이전트가 바꿀 수 없습니다.

- 실시간 리서치: `as_of = now()`
- 백테스트: `as_of = 과거 시점 T`
- 차트 학습(§37): `as_of = T`, 미래 캔들은 조회 자체가 불가능

> 이렇게 하면 "미래 정보 안 보기"가 **에이전트의 선의에 의존하지 않습니다.** 코드가 막습니다.

### 3-3. 버전 관리 (정정 데이터 처리)

같은 사실이 정정되면 **UPDATE하지 않고 새 행을 INSERT**합니다.

| id | fact_key | value | published_time | version | supersedes |
|---|---|---|---|---|---|
| 1 | AAPL:2025Q4:revenue | 124.3B | 2026-01-30 | 1 | null |
| 2 | AAPL:2025Q4:revenue | 124.1B | 2026-03-15 | 2 | 1 |

- 2026-02-01 시점 분석 → 124.3B를 본다 (당시 진실)
- 2026-04-01 시점 분석 → 124.1B를 본다
- **과거 분석이 미래에 재현 가능하다** (§50 Audit 재현성)

### 3-4. 거래일 계산

`exchange_calendars`로 처리합니다. "T+5D"는 **달력 5일이 아니라 거래일 5일**이며, 거래소마다 다릅니다 (XNYS / XKRX / XTAI). 직접 구현하면 반드시 틀립니다.

---

## 4. 데이터 파이프라인 (§18 구현)

```
[SOURCE]
   │  Provider 인터페이스 (yfinance / edgartools / news / ...)
   ▼
[COLLECTOR]  ── rate limit, retry, User-Agent(SEC 필수), robots.txt 존중
   ▼
[RAW STORAGE]  ── data/raw/{source}/{date}/*.json.gz  (원본 그대로, 불변)
   │             content_hash 계산
   ▼
[RESEARCH FIREWALL]  ★ §22
   │  ├─ trafilatura: 본문 추출 + canonical URL + 발행일
   │  ├─ 정확 중복: content_hash
   │  ├─ 근사 중복: MinHash/SimHash  ← 신디케이션 기사 탐지
   │  ├─ 스팸/SEO/AI생성 휴리스틱
   │  ├─ 티커 검증 (같은 티커 다른 회사 / 사명 변경)
   │  └─ 출처 없는 숫자 탐지
   ▼
[VALIDATION]  ── Pandera 스키마 + 범위 검사 + 이상치
   ▼
[NORMALIZATION]  ── 단위/통화/타임존(UTC 저장, 표시만 KST)
   ▼
[ENTITY RESOLUTION]  ── ticker → company_id (CIK 기준). 상장폐지/사명변경/티커 재사용 처리
   ▼
[SOURCE LINEAGE]  ★ §23  ── original_source_id 추적
   │  독립 근거 수 (independent_evidence_count) ≠ 페이지 수 (page_count)
   ▼
[POINT-IN-TIME DB]  ── 4개 타임스탬프 + version
   ▼
[KNOWLEDGE CANDIDATE]
   ▼
[VERIFICATION]  ★ §31  ── 소스 검사 / 중복 / 모순 / 근거
   ▼
[KNOWLEDGE DB]  ─── 실패 시 → [REJECTED KNOWLEDGE] (재유입 방지용으로 보존)
```

### 4-1. Source Lineage — 왜 이게 중요한가

로이터 기사 하나를 50개 사이트가 복사하면, 순진한 시스템은 **"50개 소스가 확인함"**이라고 판단합니다. 이건 완전히 틀렸습니다. 독립 근거는 **1개**입니다.

구현:
```
evidence
  ├─ evidence_id
  ├─ claim_id
  ├─ source_id            → 우리가 읽은 페이지
  ├─ original_source_id   → 원문 (canonical URL / "Reuters 보도" 명시 등으로 추적)
  ├─ independent          → boolean
  └─ tier                 → S/A/B/C/D/E
```

집계 시:
- `page_count` = 읽은 페이지 수 (50)
- `independent_evidence_count` = `DISTINCT original_source_id` (1)
- **신뢰도 계산에는 후자만 사용**

### 4-2. Source Tier — configurable

`config/source_tiers/default.yaml`에 정의하고, 코드에 하드코딩하지 않습니다.

```yaml
tiers:
  S: { weight: 1.00, can_confirm_fact: true,  examples: [sec.gov, fda.gov, 거래소, 공시] }
  A: { weight: 0.80, can_confirm_fact: true,  examples: [주요 언론, 공식 IR, 어닝콜] }
  B: { weight: 0.60, can_confirm_fact: true,  examples: [산업 전문매체] }
  C: { weight: 0.40, can_confirm_fact: false, examples: [애널리스트 코멘터리] }
  D: { weight: 0.20, can_confirm_fact: false, examples: [블로그, Substack] }
  E: { weight: 0.05, can_confirm_fact: false, examples: [Reddit, X, StockTwits] }

rules:
  # 낮은 티어는 버리지 않는다. "발견 단서"로 쓴다. (§24)
  discovery_lead_allowed: [C, D, E]
  # 확정 사실이 되려면
  confirmed_fact_requires:
    min_independent_sources: 2
    min_tier: B
    contradiction_check: required
```

**핵심**: Tier E(레딧)는 버리지 않습니다. **"이런 소문이 있다"는 것 자체가 조사 시작점**입니다.
다만 `verification_status`가 `DISCOVERY_LEAD`로 남고, 절대 `CONFIRMED_FACT`가 되지 못합니다.

---

## 5. Evidence Graph (§25, §27)

```
CLAIM ("NVDA의 데이터센터 매출이 전년 대비 X% 증가")
  │
  ├─ EVIDENCE #1 ── SOURCE (10-Q, SEC EDGAR) ── ORIGINAL: SEC (Tier S)
  ├─ EVIDENCE #2 ── SOURCE (어닝콜 트랜스크립트) ── ORIGINAL: 회사 IR (Tier A)
  └─ EVIDENCE #3 ── SOURCE (기사) ── ORIGINAL: 위 10-Q ← 독립 근거 아님
```

**강제 장치 (§25 NO EVIDENCE POLICY):**

리포트 생성 시 파이프라인이 다음을 검사합니다:

```python
# packages/evaluation/evidence_gate.py — 개념
NUMBER_PATTERN = r'\d[\d,.]*\s*(%|억|조|B|M|배|원|달러)?'

def gate(report: Report) -> Report:
    for number in extract_numbers(report.body):
        if number.evidence_id is None:
            raise EvidenceMissing(number)   # ← 리포트 발행 자체가 막힘
    return report
```

즉 **"근거 없는 숫자를 쓰지 말라"고 프롬프트로 부탁하는 게 아니라, 코드가 거부합니다.**

confidence 매핑:
| 상태 | 처리 |
|---|---|
| NO EVIDENCE | 주장 자체 금지 |
| WEAK (Tier C~E만) | `confidence: LOW` + UI에 경고 |
| CONFLICTING | 결론 내지 않고 **추가 리서치 잡을 큐에 넣음** |
| UNKNOWN | "모른다"고 명시. 이게 정답인 경우가 많다 |

---

## 6. Agent 조직 구조

### 6-1. Agent Registry (§11)

100개 이상을 **정의**할 수 있지만 **실행하지 않습니다.**

```yaml
# config/agents/sector_semiconductor_bull.yaml
id: sec_semi_bull
name: Semiconductor Bull Researcher
department: Semiconductor
sector: semiconductor
role: BULL_RESEARCHER
status: ACTIVE            # ACTIVE | REGISTERED | SLEEPING
specialties: [foundry, capex_cycle, sox_relative_strength]
skills:
  - common_chart_skill        # ★ 모든 섹터 에이전트 기본 장착 (§14)
  - sector_chart_semiconductor
  - fundamental_basic
  - source_verification
model_policy:
  default: tier_strong        # 실제 모델명이 아니라 "등급"으로 지정 ← §51
  cheap_tasks: tier_cheap
research_depth: 10
learning_target_minutes: 240
source_permissions: [S, A, B, C, D, E]
memory_namespace: agents/sec_semi_bull
```

**모델을 등급으로 지정하는 이유**: `claude-opus-5` 같은 실제 모델명을 YAML에 박으면 §51(모델 독립성)이 깨집니다. `tier_strong` / `tier_mid` / `tier_cheap` → 실제 모델 매핑은 `config/models.yaml` **한 곳**에서만 합니다.

### 6-2. Router — wake-up 방식

```
Research Job (ticker=NVDA)
   ▼
Router: 이 종목의 sector = semiconductor
   ▼
깨울 에이전트 선택:
   - sec_semi_lead    (ACTIVE)
   - sec_semi_bull    (ACTIVE)
   - sec_semi_bear    (ACTIVE)
   - technical_master (ACTIVE, 공유)
   - data_quality     (ACTIVE, 공유)
   ▼
나머지 90여 명은 SLEEPING → LLM 호출 0회
```

### 6-3. MVP ACTIVE 팀 (14명, §62)

CIO / Chief Learning Officer / Data Quality / Source Verification / Technical Master /
Semiconductor Lead·Bull·Bear / Biotech Lead·Bull·Bear / Energy Lead·Bull·Bear

나머지는 `config/agents/`에 프로필만 존재하고 `status: REGISTERED`.

---

## 7. LangGraph 워크플로

### 7-1. Research Graph (§26 확증편향 방지 내장)

```
        ┌──────────────┐
        │  INTAKE      │  ticker, as_of 고정
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ DATA GATHER  │  PITQuery(as_of)로만 접근
        └──────┬───────┘
               ▼
     ┌─────────┴─────────┐
     ▼                   ▼
┌──────────┐       ┌──────────┐
│ BULL     │       │ BEAR     │   ← ★ 서로의 결과를 못 봄 (§12)
│ RESEARCH │       │ RESEARCH │      LangGraph state를 분리 채널로 관리
└────┬─────┘       └─────┬────┘
     │                   │
     ▼                   ▼
┌──────────────────────────────┐
│ CONTRADICTION SEARCH  ★§26   │
│  Bull thesis → Bear 쿼리 생성 │
│  Bear thesis → Bull 쿼리 생성 │  ← 자동. 에이전트가 거를 수 없음
└──────────────┬───────────────┘
               ▼
        ┌──────────────┐
        │ DEBATE       │  이제서야 서로 공개. N라운드
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ EVIDENCE     │  근거 없는 숫자 제거 / 티어 검증
        │ GATE   ★§25  │  ← 통과 못 하면 리포트 발행 안 됨
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ JUDGE        │  말투가 아닌 근거의 질로 판정 (§17)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ COMMITTEE    │  Agent Trust Score 가중 (§36)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │ PREDICTION   │  Prediction Journal에 기록 (§33)
        │ JOURNAL      │
        └──────────────┘
```

**Bull/Bear 격리 구현**: LangGraph state에서 `bull_channel`과 `bear_channel`을 분리하고, DEBATE 노드 이전에는 상대 채널을 프롬프트 컨텍스트에 넣지 않습니다. 이건 프롬프트 지시가 아니라 **데이터 전달 구조**로 막습니다.

### 7-2. 그 외 그래프
- **Learning Graph** (§28~32): 커리큘럼 → 자료수집 → 검증 → Knowledge 후보 → 시험
- **Evaluation Graph** (§33~35): 1D/5D/20D/60D 스케줄 평가 → 오답 분류 → Learning Memory
- **Chart Learning Graph** (§37): 과거 윈도우 → 미래 숨김 → 예측 → 공개 → 실패분석

---

## 8. Chart Engine (§14~16, §37~38)

```
packages/chart_skills/
├─ indicators.py       # pandas-ta-classic 기본, TA-Lib 있으면 가속
├─ timeframes.py       # M / W / D / 4H / 1H / 30M / 15M / 5M / 1M 리샘플링
├─ structure.py        # HH/HL/LH/LL, 지지/저항, 추세, 레인지, 돌파/실패돌파
├─ multi_tf.py         # 상위→하위 타임프레임 종합
├─ render.py           # mplfinance → PNG (에이전트에게 보여줄 이미지)
├─ common_skill.py     # ★ 모든 섹터 에이전트가 장착
└─ sector\
    ├─ biotech.py      # FDA 이벤트 갭, 유상증자 리스크, 낮은 유통주식수, 바이너리 이벤트
    ├─ semiconductor.py# SOX 상대강도, 사이클, 어닝 갭, CapEx 사이클
    ├─ bitcoin_equity.py # BTC 상관/베타, 야간 크립토 변동, 채굴 경제성
    └─ smallcap.py     # Float, 프리마켓 거래량, RVOL, Gap%, HOD/LOD, 거래정지
```

**§38 준수**: 에이전트에게는 **이미지와 숫자를 동시에** 넘깁니다.
```python
chart_context = {
    "image_png": ...,          # mplfinance 렌더
    "ohlcv": [...],            # 원시 수치
    "indicators": {"rsi14": ..., "atr14": ..., "adx14": ...},
    "relative": {"vs_sector": ..., "vs_spx": ...},
    "structure": {"trend": "up", "last_hh": ..., "support": [...]},
}
```

**§14 마지막 문장 준수**: 프롬프트에 명시적으로 넣습니다 —
> "기술적 분석 프레임워크는 통계적 경향이지 물리 법칙이 아니다. 패턴 이름을 근거로 제시하지 말고, 표본 수와 과거 승률을 근거로 제시하라."

---

## 9. LLM Gateway & 모델 라우팅 (§51, §52, §54)

```
packages/llm_gateway/
├─ interface.py     # 우리 자체 얇은 인터페이스 (LiteLLM도 교체 가능하게)
├─ litellm_impl.py  # LiteLLM 구현체
├─ router.py        # 작업 난이도 → 모델 등급
└─ cost.py          # agent_id / job_id 별 토큰·비용 기록
```

**라우팅 규칙 (`config/models.yaml`):**

| 작업 | 처리 | 이유 |
|---|---|---|
| HTML 파싱, 본문 추출 | **코드** (trafilatura) | LLM 불필요 |
| 중복 판정 | **코드** (MinHash) | 결정론적이어야 함 |
| 지표 계산 | **코드** (pandas-ta) | LLM은 산수를 틀린다 |
| 데이터 검증 규칙 | **코드** (Pandera) | 재현성 필요 |
| 뉴스 분류/태깅 | `tier_cheap` | 단순 분류 |
| 요약 | `tier_mid` | |
| Bull/Bear thesis 합성 | `tier_strong` | 여기가 가치 있는 지점 |
| 모순 분석 | `tier_strong` | |
| 실패 원인 분석 | `tier_strong` | |
| 시험 채점 | `tier_strong` | |

**§29 "100명 × 4시간 = 400시간 LLM 호출"이 되지 않는 이유:**
1. 4시간은 **커리큘럼 분량**이지 LLM 통화 시간이 아니다
2. 커리큘럼의 대부분(문서 파싱·중복 제거·지표 계산·과거 계산)은 **코드가 처리**한다
3. SLEEPING 에이전트는 호출되지 않는다
4. Effective Learning Time에서 idle/중복/스팸/에러 루프는 **제외**된다

비용 상한: `config/learning/budget.yaml`에 일일 한도를 두고, LiteLLM 예산 기능 + 우리 `cost.py`로 이중 확인. 한도 초과 시 **작업을 큐에 남기고 중단**합니다 (조용히 실패하지 않음).

---

## 10. Pixel Office 실시간 연동 (§41~43)

### 10-1. 이벤트 흐름 — "Fake Status 금지" (§44)

```
agent_runtime에서 노드 진입/이탈 시
   ▼
AgentEvent 발행 (Postgres에 append + Redis pub/sub)
   ▼
FastAPI WS Hub가 구독
   ▼
브라우저 WebSocket
   ▼
Canvas 2D 렌더러가 캐릭터 상태/목적지 갱신
```

**핵심 원칙**: 프론트엔드는 **상태를 지어내지 않습니다.** 백엔드 이벤트가 없으면 캐릭터는 움직이지 않습니다. 데모 데이터를 쓸 때는 화면에 `MOCK DATA` 배지를 띄웁니다 (§63).

```python
# 이벤트 스키마
{
  "type": "agent.status_changed",
  "agent_id": "sec_semi_bull",
  "status": "CHARTING",           # §42 상태 목록
  "location": "chart_lab",        # 캐릭터가 이동할 곳
  "job_id": "...", "ticker": "NVDA",
  "detail": "4H 타임프레임 구조 분석",
  "ts": "2026-09-02T05:12:33Z",
  "is_mock": false                # ★ 반드시 명시
}
```

### 10-2. 상태 → 장소 매핑

| 상태 | 이동 장소 |
|---|---|
| RESEARCHING / READING | 해당 부서 자리 또는 Research Library |
| CHARTING | Chart Lab |
| 데이터 수집/검증 | Data Center |
| DEBATING | Bull/Bear Debate Room |
| 리스크 검증 | Risk Room |
| 최종 검토 | Investment Committee Room |
| CIO 검토 | CIO Office |
| LEARNING | 자기 자리 (책 애니메이션) |
| BLOCKED | 자기 자리 (빨간 느낌표) |

### 10-3. 렌더러 추상화

```typescript
// apps/web/src/office/OfficeRenderer.ts
export interface OfficeRenderer {
  mount(canvas: HTMLCanvasElement): void;
  setAgents(agents: AgentView[]): void;
  applyEvent(e: AgentEvent): void;
  destroy(): void;
}
// MVP: Canvas2DRenderer
// 캐릭터 100명 넘고 프레임 떨어지면: PixiJSRenderer 추가 (파일 하나만 늘어남)
```

---

## 11. 데이터베이스 스키마 (핵심 테이블만)

```
-- 엔티티
companies(company_id PK, cik, name, sector, industry, ...)
tickers(ticker, company_id FK, exchange, valid_from, valid_to)  ← 티커 재사용 대응

-- 소스 & 근거
sources(source_id PK, url, domain, source_type, tier, fetched_at, content_hash,
        original_source_id FK NULL, is_independent)
evidence(evidence_id PK, claim_id FK, source_id FK, excerpt, confidence, created_at)
claims(claim_id PK, subject, statement, verification_status, created_at)

-- Point-in-Time 사실
facts(fact_id PK, company_id FK, fact_key, value_num, value_text, unit,
      event_time, published_time, received_time, effective_time,
      version, supersedes FK NULL, source_id FK, confidence)
      -- INDEX (company_id, fact_key, published_time DESC)

-- 시세
bars(company_id FK, tf, ts, o,h,l,c,v, provider, received_time)
     -- PK (company_id, tf, ts)

-- 지식
knowledge(k_id PK, agent_id, namespace, statement, embedding vector(N),
          status, evidence_ids[], created_at, version)
knowledge_rejected(k_id PK, statement, reason, evidence_ids[], created_at)
          -- ★ 같은 거짓 정보 재유입 시 대조용 (§31)

-- 에이전트
agents(agent_id PK, profile_yaml, status, scores jsonb, updated_at)
agent_events(id PK, agent_id, type, status, location, job_id, ticker, detail, ts, is_mock)

-- 예측 & 평가
predictions(pred_id PK, agent_id, ticker, ts, price_at_prediction, direction,
            confidence, horizon, expected_range, thesis, bull_case, bear_case,
            catalysts[], risks[], invalidation, chart_state jsonb,
            market_regime, sector_regime, evidence_ids[])
prediction_results(pred_id FK, horizon, actual_return, direction_correct,
                   mae, mfe, calibration_error, evaluated_at)
prediction_postmortem(pred_id FK, failure_category, analysis, learned_at)

-- 감사 (§50)
audit_log(id PK, agent_id, ts, task, input_snapshot_ref, model, prompt_version,
          output_ref, evidence_ids[], knowledge_version, decision, cost_usd)

-- 비용 (§54)
llm_usage(id PK, agent_id, job_id, provider, model, prompt_tokens,
          completion_tokens, cost_usd, ts)
```

---

## 12. 보안 (§53)

- `.env`는 `.gitignore` 최상단. `.env.example`만 커밋.
- 시크릿은 `packages/shared/config.py`(Pydantic Settings) 한 곳에서만 로드.
- **로깅 필터**: 구조화 로거에 마스킹 필터를 넣어 `sk-`, `Bearer `, `api_key` 패턴을 자동으로 `***`로 치환. 실수로 찍혀도 파일에 남지 않게.
- MVP는 `localhost` 바인딩만. 외부 노출 없음.
- 커밋 전 시크릿 스캔: `scripts/precommit-secret-scan.ps1` (Phase 4)

---

## 13. 로깅 (§56)

`structlog` JSON 출력. 필수 필드:
`timestamp, request_id, job_id, agent_id, ticker, sector, operation, provider, status, latency_ms, error`

---

## 14. 테스트 전략 (§57)

| 테스트 | 무엇을 막는가 | 우선순위 |
|---|---|---|
| **Point-in-Time 테스트** | look-ahead bias. `as_of=T`로 조회 시 T 이후 데이터가 절대 안 나오는지 | ★★★ 최우선 |
| **Source Dedup 테스트** | 같은 원문 50개를 50개 독립 소스로 세는 버그 | ★★★ |
| **Research Firewall 테스트** | 스팸/중복/티커 오인 통과 | ★★★ |
| **Evidence Gate 테스트** | 근거 없는 숫자가 리포트에 들어가는지 | ★★★ |
| Chart Calculation 테스트 | 지표 계산 오류 (알려진 값과 대조) | ★★ |
| Agent Routing 테스트 | 잘못된 에이전트 wake-up / 100명 전부 깨우는 사고 | ★★ |
| Data Validation 테스트 | 스키마 위반 | ★★ |
| Learning Evaluation 테스트 | 채점 로직 | ★ |
| WebSocket 테스트 | 이벤트 전달 | ★ |
| UI 기본 테스트 (Playwright) | 페이지 렌더 | ★ |

> **상위 4개는 Phase 13 이전에 반드시 존재해야 합니다.** 이게 없으면 시스템이 조용히 틀린 답을 내고, 그걸 알아챌 방법이 없습니다.

---

## 15. Windows 실행 스크립트 (§58)

| 스크립트 | 하는 일 | 안전장치 |
|---|---|---|
| `audit.ps1` | 환경 점검 (읽기 전용) | 아무것도 변경 안 함 |
| `setup.ps1` | `.venv` 생성 → 의존성 설치 → `npm ci` → `.env` 생성 → docker 이미지 pull | 기존 `.venv` 정상이면 재생성 안 함. 포트 충돌 시 자동 우회 |
| `start.ps1` | `docker compose -p ai-stock-research-office up -d` + API + web | 다른 컨테이너 건드리지 않음 |
| `stop.ps1` | `docker compose -p ai-stock-research-office down` | **`-v` 절대 안 붙임** (볼륨 보존) |
| `health.ps1` | 각 서비스 헬스체크 + 포트 확인 | 읽기 전용 |
| `reset-local.ps1` | 이 프로젝트 볼륨만 삭제 | **`-p ai-stock-research-office` 스코프 고정. `docker system prune` 절대 사용 안 함. 실행 전 y/N 확인 프롬프트.** |
| `license-check.ps1` | 의존성 라이선스 스캔 (GPL/AGPL 탐지) | 읽기 전용 |

**§66 금지 명령 — 이 프로젝트 어떤 스크립트에도 등장하지 않습니다:**
`docker system prune -a` / `docker volume prune` / `docker container prune` / `Remove-Item C:\... -Recurse` (프로젝트 외부) / 전역 Python·Node 변경

---

## 16. 의도적으로 하지 않는 것 (그리고 이유)

| 안 하는 것 | 이유 |
|---|---|
| 마이크로서비스 전면 분리 | 1인 개발 + Windows. 프로세스가 늘수록 디버깅이 지옥이 된다. 경계는 `packages/`로 나누고 배포는 뭉쳐서 한다. |
| Kubernetes | Docker Compose로 충분하다. |
| PixiJS (MVP) | 캐릭터 14명에 WebGL 엔진은 과하다. 인터페이스만 남겨둔다. |
| Kafka/RabbitMQ | Redis + arq로 충분하다. |
| 자체 LLM 파인튜닝 | Phase 21 이후. 지금은 가치 대비 비용이 안 맞는다. |
| 실거래 연동 | §5. 별도 미래 Phase. |
| GraphQL | REST + WebSocket으로 충분. |
| Celery | Windows 공식 지원 중단. arq로 대체. |

---

## 17. Phase 4에서 즉시 만들 것

1. `C:\ai-research` 스캐폴드 + `git init`
2. `.venv` (Python 3.12) + `pyproject.toml` (최소 의존성만)
3. `docker-compose.yml` (project name `ai-stock-research-office`, 포트 5433/6380)
4. `.env.example` / `.gitignore` / `README.md`
5. `scripts/*.ps1` 전부
6. `apps/web` Next.js 스캐폴드 (로컬 설치)
7. `services/api` FastAPI 헬스체크 엔드포인트
8. 첫 커밋: `feat: initialize project scaffold`

**설치하지 않는 것**: 금융 패키지 전체, LLM SDK, TA-Lib. **Phase별로 점진적으로만** 추가합니다 (§2).
