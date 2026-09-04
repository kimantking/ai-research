# AI STOCK RESEARCH OFFICE

> 여러 AI 애널리스트가 한 사무실에서 일하는 모습을 보면서,
> 그들이 **무엇을 근거로** 그런 판단을 했는지 끝까지 따라갈 수 있는 리서치 시스템.

이 프로그램은 "주식 추천기"가 아닙니다. 실제 투자 리서치 회사처럼
데이터 수집 → 검증 → 분석 → 반대 의견 → 토론 → 근거 심사 → 기록 → 복기
를 거치도록 만든 시스템입니다.

**실제 매매 기능은 없습니다.** 리서치 · 분석 · 시뮬레이션 · 백테스트까지만 합니다.

---

## 1. 실행 방법 (이것만 알면 됩니다)

PowerShell을 열고 두 줄만 입력하세요.

```powershell
cd C:\ai-research
.\start.ps1
```

브라우저가 자동으로 열리고 **픽셀 사무실**이 나타납니다.

처음 한 번은 준비가 필요합니다.

```powershell
cd C:\ai-research
.\setup.ps1
```

끝낼 때는:

```powershell
.\stop.ps1
```

> **`.ps1` 이 "디지털 서명되지 않았습니다" 오류로 막히면** — 정상입니다.
> 인터넷에서 받은 파일이라 Windows 가 막은 것뿐입니다.
> `.\setup.bat` / `.\start.bat` 처럼 **`.bat` 을 쓰시면 됩니다**
> (같은 PowerShell 창에서 그대로 입력하셔도 되고, 더블클릭도 됩니다).
> `setup` 이 한 번 돌면 그다음부터는 `.ps1` 도 정상 동작합니다.

---

## 2. 명령어 전부

| 명령 | 하는 일 |
|---|---|
| `.\setup.ps1` | 처음 준비 (가상환경, 패키지, 포트 확인) |
| `.\start.ps1` | 실행 |
| `.\stop.ps1` | 종료 (**이 프로젝트만**) |
| `.\restart.ps1` | 재시작 |
| `.\health.ps1` | 지금 뭐가 켜져 있는지 확인 |
| `.\test.ps1` | 전체 테스트 실행 |
| `.\update.ps1` | 패키지 최신화 + 테스트 |
| `.\logs.ps1` | 로그 보기 |
| `.\fetch-data.ps1` | **실제 시세 넣기** (CSV / 공공데이터포털 / Stooq / yfinance) |
| `.\scripts\db.ps1` | 학습 저장소 상태 · 저장 · 백업 |
| `.\scripts\audit.ps1` | 내 PC 환경 점검 (읽기 전용) |
| `.\scripts\license-check.ps1` | 위험한 오픈소스 라이선스 검사 |
| `.\scripts\reset-local.ps1` | 이 프로젝트만 초기화 (확인 프롬프트 있음) |

---

## 3. 다른 프로젝트에 영향이 없는 이유

antking님 PC에는 다른 개발 프로젝트가 있습니다. 이 프로젝트는 그것들을 **절대 건드리지 않습니다.**

| 항목 | 이 프로젝트가 쓰는 값 | 왜 |
|---|---|---|
| 백엔드 포트 | **8010** | 8000은 다른 프로젝트가 쓸 확률이 높아서 |
| 프론트 포트 | **3010** | 3000 회피 |
| PostgreSQL | **5433** | 5432 회피 |
| Redis/Valkey | **6380** | 6379 회피 |
| Docker 프로젝트명 | `ai-stock-research-office` | 고유 이름 |
| 컨테이너 이름 | `airo-*` | 고유 접두사 |
| Docker 볼륨 | `airo_pgdata`, `airo_redisdata` | 고유 접두사 |
| Python | `C:\ai-research\.venv` | 이 폴더 전용 |
| Node 패키지 | `apps\web\node_modules` | 전역 설치 안 함 |

**이미 사용 중인 포트가 있으면 그 프로그램을 끄지 않고 우리가 비켜갑니다.**
`setup.ps1` 이 자동으로 다음 빈 포트를 찾아 `.env` 에 적어둡니다.

절대 실행하지 않는 명령: `docker system prune`, `docker volume prune`,
`docker container prune`, 프로젝트 폴더 밖의 `Remove-Item`.
이걸 사람이 지키는 게 아니라 **테스트가 감시합니다** (`tests/test_scripts_safety.py`).

---

## 4. 지금 무엇이 실제로 동작하나요

### 동작합니다 (테스트로 검증됨)

- **픽셀 사무실** — 캐릭터 16명이 부서를 이동하며 일합니다. 클릭하면 상세 정보가 나옵니다.
- **실시간 연동** — 백엔드에서 일어난 일이 WebSocket으로 즉시 화면에 반영됩니다. 화면이 상태를 지어내지 않습니다.
- **에이전트 학습** — 차트 문제를 풀고, 틀리면 가중치를 고치고, 시험을 봅니다. **점수가 실제 측정값입니다.**
- **Research Firewall** — 스팸·중복·복사 기사·익명 루머·출처 없는 숫자를 걸러냅니다.
- **Evidence Gate** — 근거 ID 없는 숫자가 하나라도 있으면 리포트 발행이 **차단**됩니다.
- **Bull / Bear 격리 토론** — 토론 전까지 서로의 결과를 볼 수 없습니다.
- **예측 저널** — 모든 판단을 기록하고 1D/5D/20D/60D로 채점, 실패 원인을 8종으로 분류합니다.
- **백테스트** — 신호는 T 종가, 체결은 T+1 시가. 수수료·슬리피지 반영. 미래 정보 누수 검사 포함.
- **Pattern Miner** — 조건 조합을 탐색하고 학습/검증/OOS 세 구간을 모두 통과한 것만 인정합니다.
  여기에 **walk-forward 검증**과 **다중검정 보정(BH-FDR)** 을 더했습니다.
  후보 153개를 검정하면 우위가 없어도 약 8개가 우연히 유의해 보입니다 — 그것을 걸러냅니다.
- **거래일 캘린더** — 백테스트의 `T+1` 이 정말 **다음 거래일**인지 검사합니다.
  2024년 252일 / 2025년 250일 — 공개된 사실과 일치합니다.
- **학습 영속화** — 껐다 켜도 모델 가중치·학습시간·예측 저널이 이어집니다 (SQLite 파일 하나).
- **실제 시장 데이터** — `data\market\` 에 CSV 를 넣으면 실데이터로 돌아갑니다.
  **API 키·가입·비용이 없습니다.** 7가지 품질 검사를 자동으로 합니다.
- **SEC EDGAR** — 초당 10요청 제한을 지키고, 연락처 이메일이 없으면 **요청 자체를 만들지 않습니다.**
  `filing_date`(공개일)와 `period_of_report`(실적 기간)를 절대 섞지 않습니다.
- **Point-in-Time** — 과거 분석 시 미래 데이터는 함수에 전달조차 되지 않습니다.

### 아직 아닙니다

- **실제 시장 데이터** — 지금은 합성(MOCK) 데이터입니다. 화면에 `MOCK DATA` 배지가 항상 떠 있습니다.
- **LLM 연결** — API 키가 없어도 위 기능은 전부 동작합니다. LLM은 심층 추론 단계에서만 씁니다.
- **실거래** — 구현 계획에 없습니다.

> **중요**: 지금 화면에 보이는 수익률·승률은 **가짜 데이터에서 나온 숫자**입니다.
> 실제 시장에 대해 아무것도 말해주지 않습니다. 그래서 배지를 항상 띄워둡니다.

---

## 5. 화면 설명

| 메뉴 | 내용 |
|---|---|
| **Office** | 픽셀 사무실. 캐릭터 클릭 → 오른쪽에 상세 정보 |
| **Research** | 티커 입력 → Bull/Bear 독립 분석 → 토론 → 리포트 |
| **Agents** | 정의된 에이전트 전체 목록 (177명) |
| **Learning** | 에이전트별 학습 시간·시험 점수·차트 실력 |
| **Markets** | (Phase 21 예정 — 비워둠) |
| **Data** | 데이터 공급자 연결 상태 |
| **Backtest** | 전략 백테스트 + 미래 누수 검사 결과 |
| **Patterns** | 패턴 탐색 결과 + 과적합 경고 |
| **Audit** | 승인/기각된 지식, 예측 저널, 이벤트 로그 |
| **Settings** | 시스템 상태와 켜져 있는 안전장치 |

---

## 6. 폴더 구조

```
C:\ai-research
├─ apps\web\           프론트엔드 (Next.js, 선택)
├─ services\
│   ├─ api\            백엔드 (FastAPI + standalone 두 벌)
│   │   └─ static\     픽셀 사무실 화면
│   ├─ agent_runtime\  에이전트가 실제로 일하는 곳
│   ├─ scheduler\      주기 작업
│   └─ data_worker\    데이터 수집
├─ packages\
│   ├─ agent_registry\   에이전트 프로필과 라우터
│   ├─ chart_skills\     지표 계산·시장 구조
│   ├─ learning_engine\  학습·시험·지식 승인
│   ├─ source_validation\ Research Firewall
│   ├─ evaluation\       예측 저널·Evidence Gate
│   ├─ backtest_engine\  백테스트
│   ├─ pattern_miner\    패턴 탐색
│   ├─ pit_store\        Point-in-Time 저장소
│   └─ shared\           설정·로깅·YAML
├─ config\             에이전트·섹터·소스등급·모델 설정 (YAML)
├─ docs\               문서
├─ tests\              테스트
└─ scripts\            PowerShell 스크립트
```

---

## 7. 문서

읽는 순서를 추천드립니다.

1. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — 지금 어디까지 됐는지
2. [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md) — 설치가 막힐 때
3. [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — 문제 해결
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 전체 설계
5. [`docs/DECISIONS.md`](docs/DECISIONS.md) — 왜 이렇게 만들었는지
6. [`docs/LICENSE_AUDIT.md`](docs/LICENSE_AUDIT.md) — 라이선스 위험
7. [`docs/KOREA_DATA.md`](docs/KOREA_DATA.md) — **한국 시세·공시 연결 (공공데이터포털·DART)**
8. [`docs/MARKET_DATA.md`](docs/MARKET_DATA.md) — 실제 시세 넣는 법 (CSV·Stooq)
9. [`docs/PERSISTENCE.md`](docs/PERSISTENCE.md) — 학습이 이어지는 원리
10. [`docs/STATISTICS.md`](docs/STATISTICS.md) — 다중검정 보정·walk-forward
11. [`docs/CALENDAR.md`](docs/CALENDAR.md) — 거래일 캘린더
12. 나머지 주제별 문서는 `docs\` 폴더에

---

## 8. 이 시스템이 지키는 원칙

1. **근거 없는 숫자는 리포트에 넣을 수 없다** — 부탁이 아니라 코드가 막습니다.
2. **미래를 볼 수 없다** — 과거 분석 시 미래 데이터가 함수에 전달되지 않습니다.
3. **한쪽 의견만 듣지 않는다** — Bull이 나오면 Bear 검색어가 자동 생성됩니다.
4. **복사 기사 50건은 근거 1건이다** — 원문을 추적해서 셉니다.
5. **모르면 모른다고 한다** — UNKNOWN도 정답입니다.
6. **가짜 데이터를 진짜처럼 보여주지 않는다** — MOCK 배지는 끌 수 없습니다.
7. **표본이 적으면 점수를 높게 주지 않는다** — 운을 실력으로 착각하지 않기 위해.

---

## 9. 라이선스 주의

이 프로젝트는 MIT / Apache-2.0 / BSD 계열만 사용합니다.

**의도적으로 배제한 것들:**
- **OpenBB** — AGPL-3.0. 웹서비스로 제공만 해도 전체 소스 공개 의무가 생길 수 있습니다.
- **vectorbt** — Commons Clause. 상업적 판매가 금지됩니다.
- **nautilus_trader** — LGPL-3.0. 파이썬 import 시 법적 회색지대.

자세한 내용은 [`docs/LICENSE_AUDIT.md`](docs/LICENSE_AUDIT.md).

---

## 10. 면책

이 소프트웨어는 **연구·교육 목적**입니다.
투자 자문이 아니며, 어떤 수익도 보장하지 않습니다.
투자 판단과 그 결과는 전적으로 사용자 본인의 책임입니다.
