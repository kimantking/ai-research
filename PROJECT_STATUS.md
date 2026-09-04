# PROJECT STATUS

> 세션이 끊기거나 새로 시작해도 **이 파일만 읽으면 이어서 작업**할 수 있습니다.

- 최종 갱신: **2026-09-04** (한국 데이터 연결 — 공공데이터포털 시세 + DART 공시)
- 현재 Phase: **Phase 0~23 완료.** 남은 것은 LLM 연결(API 키 필요) 뿐입니다
- 테스트: **412개 + 인수 92개 전부 통과** (Python 3.11 / 3.12 / 3.13 에서 각각 확인)
- Blocker: **없음** (아래 "사용자 결정 대기" 참고)

---

## 1. 한눈에

| 영역 | 상태 | 근거 |
|---|---|---|
| 환경 Audit 스크립트 | ✅ | `scripts/audit.ps1` (읽기 전용) |
| GitHub Deep Research | ✅ | `docs/GITHUB_RESEARCH.md` — 22개 저장소 |
| License Audit | ✅ | `docs/LICENSE_AUDIT.md` — RED 3건 배제 |
| Architecture | ✅ | `docs/ARCHITECTURE.md` |
| Repository Scaffold | ✅ | 전체 트리 생성 |
| Backend (2벌) | ✅ | FastAPI + standalone, 로직 공유 |
| Pixel Office | ✅ | 실제 렌더링 확인 (스크린샷) |
| Realtime (WebSocket) | ✅ | 원시 소켓 클라이언트로 검증 |
| Agent Registry | ✅ | 177명 / ACTIVE 16명 / 49섹터 |
| Research Firewall | ✅ | 25개 테스트 |
| Evidence Gate | ✅ | 차단 동작 검증 |
| Bull/Bear 격리 토론 | ✅ | 채널 분리 |
| Chart Engine | ✅ | 지표 24개 테스트 |
| Learning Engine | ✅ | 실제 학습 동작 확인 |
| Prediction Journal | ✅ | Trust Score 산출 |
| Point-in-Time | ✅ | PIT Store + 누수 테스트 |
| Backtest Engine | ✅ | T+1 체결, 누수 감시 |
| Pattern Miner | ✅ | 3구간 검증 + 과적합 방지 |
| Audit | ✅ | 지식/예측/이벤트 추적 |
| Cost Control | ✅ | 현재 $0, 상한 장치 동작 |
| 외부 수집기 어댑터 | ✅ | Agent Reach — 선택 설치, 23개 테스트 |
| Security | ✅ | 마스킹·경로탈출·스크립트 감시 |
| PowerShell 스크립트 | ✅ | 26개, 구문검사 통과 (BOM+CRLF) |
| 문서 | ✅ | 29개 |
| 거래일 캘린더 | ✅ | NYSE/KRX. 2024년 252일·2025년 250일 실측 일치 |
| 학습 영속화 | ✅ | SQLite. 껐다 켜도 학습이 이어짐 |
| 실제 시장 데이터 | ✅ | CSV / Stooq / yfinance 3종. 품질검사 포함 |
| SEC EDGAR | ✅ | 초당 10요청·UA 강제·공시일 분리 |
| **한국 시세 (공공데이터포털)** | ✅ | 금융위 공식·무료. 키 인코딩 자동 판별 |
| **한국 공시 (DART)** | ✅ | 금감원 공식·무료. 접수일자 없이는 PIT 거부 |
| 패턴 통계 관문 | ✅ | walk-forward + BH-FDR 다중검정 보정 |
| **LLM 연결** | ⬜ | **Phase 10 — API 키 필요 (유일한 미완)** |
| Next.js 프론트 | 🟡 | 스캐폴드만. 검증 못 함 (아래 참고) |
| PostgreSQL 영속화 | 🟡 | SQLite 로 대체 완료. 다중 사용자 때 필요 (D-031) |

---

## 2. 완료된 작업

### Phase 0 — 환경 Audit
- `scripts/audit.ps1` 작성 (읽기 전용, 설치/삭제 없음)
- Global Python 과 Project .venv 를 **구분해서** 보고
- 포트 10개 사용 현황 검사
- ⚠️ **사용자 PC 에서 아직 실행되지 않았습니다** (개발은 클라우드에서 진행)

### Phase 1~2 — GitHub Research & License Audit
- 22개 저장소를 라이선스 원문까지 확인
- 🔴 배제: **OpenBB(AGPL-3.0)**, **vectorbt(Commons Clause)**, **nautilus_trader(LGPL-3.0)**
- 🟢 채택: LangGraph, LiteLLM, edgartools, pandas-ta-classic, TA-Lib,
  exchange_calendars, QuantStats, PyPortfolioOpt, mplfinance

### Phase 3~4 — Architecture & Scaffold
- 포트 8010/3010/5433/6380, 컨테이너 `airo-*`, 볼륨 `airo_*`
- Docker Compose project `ai-stock-research-office`

### Phase 5~9 — Backend / Pixel Office / Agent Runtime
- 서버 2벌 (`main.py` FastAPI / `standalone.py` 표준 라이브러리)
- 공유 로직 `routes.py` — 두 서버 응답이 달라질 수 없음
- WebSocket 직접 구현 (RFC 6455 예제값 검증)
- 픽셀 사무실 21개 공간, 18개 상태, Right Drawer
- 에이전트 177명 정의 / 16명 ACTIVE

### Phase 10~13 — Learning / Prediction / Chart / Pattern
- 온라인 로지스틱 회귀 기반 실제 학습 (LLM 불필요)
- Effective Learning Time (idle·중복·스팸 제외)
- 시험 2종 (차트 out-of-sample / 출처 검증)
- 예측 저널 + 8종 실패 분류 + Trust Score
- Pattern Miner 3구간 검증

### Phase 5b·11·12·20b·21 — 영속화 / 캘린더 / EDGAR / 통계 / 실데이터
- **SQLite 영속화** — 껐다 켜도 모델 가중치·학습시간·예측 저널이 이어집니다
- **거래일 캘린더** — NYSE(1970~2035) / KRX(2015~2035). 백테스트 T+1 검증
- **실데이터 3종** — CSV 파일 / Stooq / yfinance. 7가지 품질 검사 포함
- **SEC EDGAR** — 초당 10요청, UA 이메일 강제, filing_date 와 period_of_report 분리
- **통계 관문 3개 추가** — walk-forward, 겹치는 표본 보정, BH-FDR 다중검정 보정

### 한국 데이터 (2026-09-04)
- **공공데이터포털 금융위 주식시세** — 페이징·중복병합·품질검사·XKRX 캘린더 연동
  · serviceKey Encoding/Decoding **자동 판별** (이 API 최대의 함정, D-039)
  · JSON 요청에 XML 오류가 오는 경우까지 사유를 한국어로 해석
- **DART 전자공시** — 목록·재무제표·회사코드(ZIP) 변환
  · **접수일자(rcept_dt) 없이는 PIT 레코드를 만들지 않습니다** (D-040)
- 로컬 스텁 서버로 전체 흐름 실측: 시세 245봉 적재 → 품질 문제 0 →
  PIT 저장 → 장 마감 전 조회 차단 확인 → 공시 2건 조회 → 회사코드 변환

### Phase 17~20 — Backtest / Security / Windows
- 백테스트 엔진 (T 신호 → T+1 체결, 비용 반영, 누수 감시)
- 시크릿 마스킹, 경로 탈출 차단, 입력 검증
- PowerShell 스크립트 21개 (UTF-8 BOM + CRLF) + ASCII `.bat` 래퍼 8개

---

## 3. 실측 결과 (합성 데이터 기준)

```
에이전트:        177명 정의 / 16명 ACTIVE / 49섹터
테스트:          412개 통과 + 인수 92건 통과 (3.11/3.12/3.13)
Technical Master: 표본 213건, 방향 정확도 60.6%,
                 캘리브레이션 오차 0.065, Trust Score 56.7
실패 분류:       TREND_REVERSAL 31, RANGE_WHIPSAW 10,
                 FAILED_BREAKDOWN 11, FAILED_BREAKOUT 9,
                 VOLATILITY_SHOCK 7, TIMING_ERROR 7,
                 NOISE_LEVEL_MOVE 6, OVERCONFIDENCE 3
출처 검증 시험:   90/100
Pattern Miner:   후보 153개 → STRONG 5, 나머지 기각
                 (walk-forward 8개 탈락 / 다중검정 보정 43개 탈락)
거래일 캘린더:    2024년 252일, 2025년 250일 - 공개 사실과 일치
영속화:          SQLite. 재시작 후 에이전트 16명·예측 925건 복구 확인
LLM 호출:        0회 / 비용 $0
```

---

## 4. 수정한 버그 (개발 중 발견)

| # | 문제 | 수정 |
|---|---|---|
| 1 | Bull/Bear 근거 ID 가 중복 (양쪽 다 EV001) | 전체 순차 부여 |
| 2 | 복기할 때마다 채점이 추가돼 성적 부풀림 (213 → 368) | 같은 horizon 은 덮어쓰기 |
| 3 | Evidence Gate 가 단위 없는 숫자를 못 잡음 (검사 0건) | 패턴 확장 → 12건 검출 |
| 4 | 근거가 마침표 뒤에 오면 다른 문장으로 분리돼 오탐 | 태그만 있는 조각을 앞 문장에 병합 |
| 5 | 16명이 한 방에 몰림 | 시작 단계 위상 분산 + 역할별 루틴 |
| 6 | 캘리브레이션 지표가 동전던지기와 구별 안 됨 (0.48) | 구간별 ECE → 0.065 |
| 7 | `setup.ps1` 에 가드 없는 `Remove-Item -Recurse` | `Assert-InsideProject` 도입 |
| 8 | 표본 12건짜리 패턴이 STRONG 승격 | 홀드아웃 최소 25건 + REDUNDANT 판정 |
| 9 | Node/pip 없으면 `setup.ps1` 이 "실패" 로 끝남 (실제로는 정상 실행 가능) | `$fatal` / `$degraded` 분리 — 선택 기능 누락은 `exit 0` |
| 10 | standalone 모드인데 `start.ps1` 이 `/docs` (FastAPI 전용) 주소를 안내 | `$hasSwagger` 로 모드별 안내 분기 |
| 11 | **실사용자 첫 실행 실패** — 다운로드한 `.ps1` 이 실행 정책에 막힘 (`PSSecurityException`) | `setup` 0단계에서 프로젝트 내부 스크립트만 `Unblock-File` + `.bat` 안내 강화 |
| 12 | `.bat` 이 성공하면 창이 즉시 닫혀 출력을 못 봄 | 조건 없는 `pause` |
| 13 | Python **3.13 사용자가 차단됨** (`-eq '3.12'` 정확히 일치 요구) | 3.12 → 3.13 → 3.11 순서로 탐색. 3.11 이상이면 진행 |
| 14 | **★ 모든 `.ps1` 이 Windows PowerShell 5.1 에서 ParserError** — BOM 없는 UTF-8 을 CP949 로 읽어 줄바꿈이 삼켜짐 (318줄 → 314줄) | 21개 전부 **UTF-8 BOM + CRLF** 로 저장. 인코딩 테스트 4개로 고정 (D-030) |
| 15 | 콘솔에서 `—` 가 `?` 로 깨짐 (CP949 미지원 문자) | `-` 로 대체 |
| 16 | **실데이터 2종목 넣으면 화면이 "LIVE DATA"** — 나머지 7종목은 여전히 합성인데 초록불 | `data_mode` MOCK/MIXED/REAL 3단계 (D-035) |
| 17 | `data_mode` 를 `system_health()` 에 안 넣어 매 틱 갱신 시 MOCK 으로 되돌아감 | 갱신 경로에도 포함 |
| 18 | 2:1 분할이 정확히 -50.0% 라 `> 0.5` 경계에서 빠져나감 (가장 흔한 경우가 미탐지) | `>=` 로 수정 (D-034) |
| 19 | `start.ps1` 이 standalone 모드에서 없는 `/docs` 를 안내 | 모드별 분기 |
| 20 | 백엔드 창이 접근 로그로 도배되고 `[32mINFO[0m` 처럼 깨져 **진짜 오류가 묻힘** | `--no-access-log` + `NO_COLOR` + 안내 헤더 |
| 21 | **★ 백엔드가 아예 안 뜸** — 19번 수정으로 `-Command` 문자열이 길어지면서(따옴표·세미콜론·괄호·한글) 새 창 전달 중 깨짐 | 실행기를 별도 파일(`_run-backend.ps1`)로 분리. `-File` + 단순 인자만 전달 |
| 22 | 쓰지도 않는 Docker 컨테이너를 기본으로 띄우려다 포트 충돌 빨간 오류 | SQLite 를 쓰므로 Docker 는 `-WithDocker` 옵션일 때만 |

---

## 5. 알려진 제한 (정직하게)

| 제한 | 영향 | 언제 해결 |
|---|---|---|
| **LLM 미연결** | 심층 추론·토론이 규칙 기반으로 동작 | **API 키 필요 (비용)** |
| **기본 데이터는 여전히 합성** | CSV 를 넣기 전까지는 MOCK. 화면 배지가 MOCK/MIXED/REAL 로 정확히 구분 | `data\market\` 에 CSV 투입 |
| **모든 외부 API 실연결 미검증** | 개발 환경이 외부망 차단이라 공공데이터포털·DART·Stooq·SEC 어디에도 접속해 보지 못했습니다. **파서·오류처리·PIT 규칙은 실제 응답 형식과 로컬 스텁으로 전량 검증** | 키 넣고 첫 실행 시 확인 |
| **한국 데이터는 키 필요** | `DATA_GO_KR_KEY` / `DART_API_KEY` 를 `.env` 에 넣어야 동작. 둘 다 무료 | `docs\KOREA_DATA.md` |
| **Next.js 앱 미검증** | npm 접근이 막혀 빌드 확인 못 함. **백엔드가 직접 서빙하는 화면은 검증됨** | 사용자 PC 에서 확인 |
| **분할·배당 조정 미구현** | 분할을 **탐지**만 하고 **조정**은 하지 않습니다 | 다음 단계 |
| **KRX 캘린더 2015~2035** | 음력 공휴일은 계산 불가라 표 기반. 범위 밖은 **예외를 던집니다**(추측 안 함) | 표 갱신 |
| **분봉·실시간 없음** | 일봉만 지원 | 다음 단계 |
| **환경 Audit 미실행** | 사용자 PC 상태를 아직 모름 | `audit.ps1` 실행 시 |

---

## 6. 사용자 결정 대기

| # | 항목 | 왜 필요한가 |
|---|---|---|
| **A-1** | `audit.ps1` 실행 후 결과 공유 | PC 환경 판정 |
| **A-2** | lightweight-charts 채택 여부 | UI 에 TradingView 표기가 들어감. 싫으면 uPlot(MIT) |
| **A-3** | **LLM API 키** | 비용 발생. 없어도 시스템은 동작 |
| **A-4** | 유료 데이터 API | 비용 발생 |
| **A-5** | 외부 공개 배포 | yfinance 약관 등 선결 필요 |

**A-3 외에는 지금 결정하지 않으셔도 됩니다.**

---

## 7. 다음에 할 일 (우선순위)

1. **한국 데이터 연결** ★ 진행 중 — 키 발급만 하시면 됩니다 (무료)
   - `DATA_GO_KR_KEY` (data.go.kr) / `DART_API_KEY` (opendart.fss.or.kr)
   - 자세한 절차: `docs\KOREA_DATA.md`
   - 키 없이도 CSV 방식은 바로 됩니다 (`data\market\` → `.\fetch-data.bat`)
2. **Phase 10 — LLM 연결** ★ **API 키 필요 (비용 발생 — 승인 대기 중)**
   - LiteLLM + `llm_gateway` 인터페이스는 이미 준비돼 있습니다
3. **분할·배당 조정** — 이벤트 테이블을 만들어 명시적으로 조정
4. **거시지표(FRED)** — 약관 확인 후 연결
5. **PostgreSQL** — 여러 대에서 같은 데이터를 볼 때 (D-031)

---

## 8. 이어서 작업하는 방법

```powershell
cd C:\ai-research
.\test.ps1        # 먼저 전부 통과하는지 확인
.\start.ps1       # 실행해서 눈으로 확인
```

그다음 이 파일의 **7번 "다음에 할 일"** 부터 진행하면 됩니다.

설계 의도가 궁금하면 `docs/DECISIONS.md` 를 보세요.
왜 그렇게 만들었는지 40개 결정이 전부 기록되어 있습니다.
