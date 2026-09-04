# LICENSE AUDIT — AI STOCK RESEARCH OFFICE

- 감사일: **2026-09-02**
- 감사자: Claude (Open Source License Auditor 역할)
- 확인 방법: GitHub 저장소 페이지의 라이선스 표기 확인. AGPL 등 위험 항목은 **LICENSE 원문 파일을 직접 열어 확인**.

> ⚠️ **법적 고지**
> 저는 변호사가 아닙니다. 이 문서는 오픈소스 라이선스에 대한 **기술적 정리**이며 법률 자문이 아닙니다.
> 이 시스템을 상업적으로 배포하거나 공개 서비스로 운영하기 전에는 **반드시 전문가 검토**를 받으시기 바랍니다.
> 특히 아래 RED 항목은 실제 법적 리스크가 있습니다.

---

## 분류 기준

| 등급 | 의미 | 허용 행위 |
|---|---|---|
| 🟢 **GREEN** | permissive. 상업 이용·수정·비공개 배포 자유 | 직접 dependency 추가, 코드 인용/수정 병합 모두 가능 |
| 🟡 **YELLOW** | 조건부. 특정 의무를 지키면 사용 가능 | 의무 이행 후 사용. 의무를 문서에 명시 |
| 🔴 **RED** | copyleft/비오픈소스 조항. 우리 코드에 전염될 수 있음 | **코드 직접 병합 금지.** 아키텍처·아이디어 참고만 |

---

## 1. 🟢 GREEN — 직접 통합 가능

| # | Repository | Version/기준 | License | 상업 이용 | 수정 시 공개 의무 | 배포 의무 | 네트워크/SaaS 영향 | 귀속 표기 | 통합 권고 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `langchain-ai/langgraph` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | **직접 의존 (핵심)** |
| 2 | `BerriAI/litellm` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | **직접 의존 (핵심)** |
| 3 | `dgunning/edgartools` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | **직접 의존 (핵심)** |
| 4 | `xgboosted/pandas-ta-classic` | 0.6.20 (2026-05-20) | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | **직접 의존 (핵심)** |
| 5 | `TA-Lib/ta-lib-python` | 조사일 main | BSD-2-Clause | ✅ | ❌ | ❌ | 없음 | 저작권 고지 유지 | **선택적 의존 (가속)** |
| 6 | `gerrymanoim/exchange_calendars` | 조사일 main | Apache-2.0 | ✅ | ❌ | ❌ | 없음 | NOTICE 유지 | **직접 의존 (필수)** |
| 7 | `ranaroussi/quantstats` | 조사일 main | Apache-2.0 | ✅ | ❌ | ❌ | 없음 | NOTICE 유지 | **직접 의존** |
| 8 | `robertmartin8/PyPortfolioOpt` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | 직접 의존 (Phase 19+) |
| 9 | `matplotlib/mplfinance` | 조사일 master | Matplotlib License (BSD 계열 permissive, PSF 변형) | ✅ | ❌ | ❌ | 없음 | 저작권 고지 유지 | **직접 의존** |
| 10 | `microsoft/qlib` | v0.9.0 표기 | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | 개념 참고 → 필요 시 부분 의존 |
| 11 | `pixel-agents-hq/pixel-agents` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | (코드 사용 시) 사본 포함 | **아키텍처 참고** |
| 12 | `Pixel-Process-UG/agent-office` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | (코드 사용 시) 사본 포함 | 참고 |
| 13 | `fakeou/agent-office` | v0.1.9 (2026-03-24) | MIT | ✅ | ❌ | ❌ | 없음 | (코드 사용 시) 사본 포함 | 참고 |
| 14 | `TauricResearch/TradingAgents` | v0.3.1 (2026-07) | Apache-2.0 | ✅ | ❌ | ❌ | 없음 | NOTICE 유지 | **설계 참고** (병합 안 함) |
| 15 | `virattt/ai-hedge-fund` | 조사일 main | MIT | ✅ | ❌ | ❌ | 없음 | (코드 사용 시) 사본 포함 | 설계 참고 |
| 16 | `pixijs/pixijs` | 8.x | MIT | ✅ | ❌ | ❌ | 없음 | 라이선스 사본 포함 | 조건부 (성능 필요 시) |
| 17 | `ranaroussi/yfinance` | 조사일 main | Apache-2.0 (**코드만**) | ✅ | ❌ | ❌ | 없음 | NOTICE 유지 | 🟡 **데이터 조건은 아래 별도** |

**Apache-2.0 공통 의무 (5, 6, 7, 14, 16, 17 해당):**
- `LICENSE` 사본 포함
- 원본에 `NOTICE` 파일이 있으면 그 내용을 우리 배포물에 포함
- 파일을 수정했다면 "변경됨" 표시
- 특허 조항: 이 소프트웨어에 대해 특허 소송을 걸면 라이선스가 종료됨

**실행 항목**: `C:\ai-research\THIRD_PARTY_LICENSES.md` 파일을 만들어 위 라이선스 전문을 모아둔다. (Phase 4)

---

## 2. 🟡 YELLOW — 조건 확인 후 사용

### 2-1. `tradingview/lightweight-charts` — Apache-2.0 **+ 귀속 표기 의무**
- **조건**: README와 라이선스가 **TradingView를 제품 제작자로 명시할 것**을 요구.
  - NOTICE 파일의 "attribution notice"를 포함
  - **사용자에게 보이는 페이지에 https://www.tradingview.com/ 링크**를 넣을 것
  - 차트의 `attributionLogo` 옵션 사용 권장
- **영향**: 우리 UI(§44 "premium dark research terminal")에 TradingView 로고/링크가 들어간다.
- **판단**: 사용 가능. 단 **사용자 확인 필요** → 원하지 않으면 대안:
  - `uPlot` (MIT, 초경량, 귀속 의무 없음)
  - 자체 Canvas 차트 (이미 mplfinance로 서버 렌더도 하므로 프론트 차트는 단순해도 됨)
- **결정 상태**: ⏳ **사용자 확인 대기** (DECISIONS.md D-007)

### 2-2. `ranaroussi/yfinance` — 코드는 Apache-2.0, **데이터는 별개**
- **코드 라이선스**: Apache-2.0 🟢 문제 없음
- **⚠️ 데이터 이용 조건**: README가 명시 —
  - yfinance는 Yahoo, Inc.와 무관하며, 사용자가 **Yahoo의 이용약관을 직접 확인할 책임**이 있다.
  - "Yahoo! finance API is **intended for personal use only**"
  - 도구 자체는 "research and educational purposes" 용도로 제시됨
- **실제 리스크**: 이건 라이선스 문제가 아니라 **서비스 약관(ToS) 문제**다. 개인 연구용으로 로컬에서 돌리는 것과, 이 데이터를 제3자에게 서비스하는 것은 완전히 다르다.
- **판단**:
  - ✅ 개발/MVP/개인 리서치: 사용 OK
  - ❌ 공개 서비스 / 상업 배포 / 데이터 재배포: **금지**
  - → 반드시 **Provider 인터페이스 뒤**에 두고, 교체 가능하게 설계 (§21)
  - → UI에 데이터 출처와 "개인 연구용" 표시
- **결정 상태**: ✅ 채택 (MVP 한정)

### 2-3. `AI4Finance-Foundation/FinGPT` — 코드 MIT, **모델/데이터셋은 별도**
- **코드**: MIT 🟢
- **⚠️ 함정**: 모델 가중치는 Llama2 / Falcon / Bloom / ChatGLM2 / Qwen 기반이며 **각 베이스 모델의 라이선스가 따로 적용**된다.
  - Llama 계열: Meta Community License (월간 활성 사용자 수 조건 등 별도 제약)
  - ChatGLM 계열: 별도 상업 이용 조건
  - HuggingFace 데이터셋: 데이터셋별 개별 라이선스
- **판단**: 🟡 **개념 참고만.** 실제로 모델을 다운로드해 사용하기로 결정하는 순간 **해당 베이스 모델 라이선스를 다시 감사**한다.
- **결정 상태**: ⏸️ 보류 (Phase 21 이후)

### 2-4. `Panniantong/agent-reach` — MIT (표기), **버전 미고정** ⚠️
- **라이선스**: 저장소 페이지 표기 **MIT**. ⚠️ **LICENSE 원문은 직접 확인하지 못했습니다** (접근 승인 실패)
- **버전**: ⚠️ **고정되지 않음.** 공식 설치가 `archive/main.zip` 이라 설치 시점의 최신 코드를 그대로 실행합니다
- **통합 방식**: 🟡 **별도 프로세스 (CLI 호출)**. 우리 코드에 **병합하지 않습니다**
  → 라이선스가 나중에 바뀌어도 우리 코드는 영향받지 않습니다
- **추가 위험 (라이선스와 별개)**:
  - Twitter/Instagram/LinkedIn/샤오홍슈는 **세션 쿠키 저장** 필요 → 약관 위반·계정 정지 위험
  - 도구 문서 스스로 "부계정 사용"을 권장 — 위험 인정
  - Jina Reader / Exa 등 **제3자 서비스 경유** → 조회 대상이 외부에 노출
- **우리 정책**: 선택 설치, 쿠키 채널 기본 차단, `--system` 금지,
  수집 결과는 **전부 Research Firewall 통과 + 우리 규칙으로 등급 재판정**
- **결정 상태**: 🟡 조건부 채택 (Phase 21 에서 실측 후 최종 판단)
- 상세: `docs/AGENT_REACH.md`

### 2-5. `microsoft/qlib` — MIT 🟢이나 유지보수 리스크
- 라이선스는 완벽하다. **리스크는 법적인 게 아니라 유지보수 쪽**이다.
- 정식 릴리스 태그가 **v0.9.0 (2022-12-09)** 로 표기됨. Python 3.12는 지원 목록에 있음.
- **판단**: 라이선스 GREEN, 그러나 **핵심 경로에 두지 않는다.** Pattern Miner(Phase 20)에서 선택적으로만.

---

## 3. 🔴 RED — 코드 직접 병합 금지

### 3-1. `OpenBB-finance/OpenBB` — **AGPL-3.0** ⚠️ 최고 위험
**LICENSE 원문 직접 확인함**: GNU Affero General Public License Version 3, Copyright (c) 2021-2025 OpenBB Inc.

| 항목 | 내용 |
|---|---|
| 상업 이용 | 조건부 가능 (소스 공개 시) |
| 수정 시 공개 의무 | ✅ **있음** |
| 배포 시 공개 의무 | ✅ **있음** |
| **네트워크/SaaS 영향** | ✅ **있음 — 이게 핵심 위험** |
| Share-alike | ✅ 파생물도 AGPL-3.0이어야 함 |
| 특허 | 기여자가 로열티 프리 특허 허여 |

**AGPL Section 13 (네트워크 조항) 원문 취지:**
> 프로그램을 수정하고, 사용자가 **컴퓨터 네트워크를 통해 원격으로 상호작용**하게 한다면, 그 사용자들에게 **당신 버전의 Corresponding Source를 받을 기회를 명시적으로 제공**해야 한다.

**우리 프로젝트에 대한 구체적 위험:**
1. 이 시스템은 Next.js + FastAPI **웹 서비스**다 → 정확히 AGPL Section 13이 겨냥하는 형태다.
2. OpenBB 코드를 `services/api` 안에 넣으면 → **AI STOCK RESEARCH OFFICE 전체 소스코드를 사용자에게 공개할 의무**가 발생할 수 있다.
3. 일반 GPL과 다르다: GPL은 "배포"할 때만 걸린다. AGPL은 **혼자 서버에 올려 남이 접속하게만 해도** 걸린다.

**결정: 🔴 코드 직접 병합 절대 금지.**

**허용되는 것:**
- ✅ **아키텍처 읽고 배우기** — OpenBB의 provider 추상화 / 데이터 표준화 패턴은 우리 §21 설계에 좋은 교재다. **읽는 것은 위반이 아니다.**
- ⚠️ 완전 분리된 별도 서비스로 HTTP 통신 — 이론상 가능하나 "aggregate vs derivative work" 판단이 회색지대. **MVP에서는 아예 사용하지 않는다.**

### 3-2. `polakowo/vectorbt` — **Apache-2.0 + Commons Clause** ⚠️
- **Commons Clause**는 OSI 승인 오픈소스가 **아니다.** Apache-2.0 위에 덧씌워진 추가 제약이다.
- **제약 내용**: 이 소프트웨어에 **실질적으로 기반한 제품/서비스를 판매하는 것을 금지**한다. ("Sell" = 소프트웨어 기능에서 가치의 전부/상당부분이 파생되는 제품·서비스의 대가 수령)
- 오픈소스판은 상용 **vectorbt PRO**의 커뮤니티 에디션이다.
- **우리에 대한 위험**: antking님이 나중에 이 시스템을 유료 서비스/제품으로 만들 가능성이 조금이라도 있으면, **지금 넣으면 나중에 통째로 걷어내야 한다.**
- **결정: 🔴 미채택.** 백테스트는 우리가 직접 만들거나 permissive 대안을 쓴다.

### 3-3. `nautechsystems/nautilus_trader` — **LGPL-3.0** ⚠️
- LGPL은 GPL보다 약하다: **라이브러리를 수정하지 않고 링크만 하면** 우리 코드를 공개할 의무는 없다.
- **그러나 파이썬에서는 회색지대다**: Python `import`가 "동적 링크"인지 "결합 저작물"인지에 대한 명확한 판례가 부족하다. 또 LGPL은 사용자가 **라이브러리를 교체할 수 있어야 한다**는 요구가 있는데, 컨테이너로 배포하면 이 요구 충족이 애매해진다.
- **판단**: 🔴 **현재 미채택.** 기술적으로 훌륭하지만 **우리는 실거래를 안 하므로 이 엔진의 핵심 가치를 쓸 일이 없다.** 법적 회색지대를 감수할 이유가 없다.

### 3-4. `QuantConnect/Lean` — Apache-2.0 🟢 (라이선스는 문제없음)
- **라이선스상 RED가 아니다.** Apache-2.0으로 깨끗하다.
- **미채택 사유는 순수하게 기술적 복잡도**: C#/.NET 런타임 추가, 실거래 지향 설계, 우리에게 필요 없는 기능 대부분.
- 이 표에 적어두는 이유는 **"라이선스 때문에 뺀 게 아니다"**를 명확히 하기 위함.

---

## 4. 인프라 / 기반 기술 라이선스

| 기술 | License | 위험 | 비고 |
|---|---|---|---|
| Python 3.12 | PSF License | 🟢 없음 | |
| Node.js | MIT | 🟢 없음 | |
| Next.js | MIT | 🟢 없음 | Vercel 소유이나 MIT |
| React | MIT | 🟢 없음 | |
| TypeScript | Apache-2.0 | 🟢 없음 | |
| FastAPI | MIT | 🟢 없음 | |
| Pydantic | MIT | 🟢 없음 | |
| SQLAlchemy | MIT | 🟢 없음 | |
| PostgreSQL | PostgreSQL License (BSD 계열) | 🟢 없음 | |
| **pgvector** | PostgreSQL License | 🟢 없음 | |
| Redis | ⚠️ **확인 필요** | 🟡 | Redis 라이선스가 최근 몇 년간 변경되어 왔음 (BSD → RSALv2/SSPL → AGPL 논의). **Phase 5 착수 시 사용 버전의 라이선스 원문을 직접 확인해야 함.** 우려되면 **Valkey**(BSD-3-Clause, Redis 포크)로 대체 가능. |
| pandas | BSD-3-Clause | 🟢 없음 | |
| numpy | BSD-3-Clause | 🟢 없음 | |
| Docker Engine | Apache-2.0 | 🟢 없음 | |
| **Docker Desktop** | ⚠️ 상용 조건 | 🟡 | 대기업(직원 250명 초과 또는 연매출 1천만 달러 초과)은 유료 구독 필요. **antking님은 1인 사업자이므로 무료 사용 대상.** |
| DuckDB | MIT | 🟢 없음 | |
| Playwright | Apache-2.0 | 🟢 없음 | |
| trafilatura | Apache-2.0 | 🟢 없음 | |
| datasketch | MIT | 🟢 없음 | |
| arq | MIT | 🟢 없음 | |
| Pandera | MIT | 🟢 없음 | |
| uv | MIT / Apache-2.0 | 🟢 없음 | |
| uPlot | MIT | 🟢 없음 | lightweight-charts 대안 |

> **Redis 항목은 반드시 Phase 5에서 재확인하십시오.** 제가 최신 라이선스 상태를 추측으로 적지 않았습니다. Valkey라는 완전 BSD 대안이 존재하므로 최악의 경우에도 막히지 않습니다.

---

## 5. 데이터 소스 라이선스 (코드와 별개로 중요)

| 소스 | 이용 조건 | 재배포 | 판단 |
|---|---|---|---|
| **SEC EDGAR** | 무료, 초당 10 요청, User-Agent에 연락처 필수. 공식 확인: "free to access and reuse" | ✅ 자유 | 🟢 **Tier S. 최우선 채택** |
| Yahoo Finance (yfinance 경유) | 개인 사용 목적 명시 | ❌ 금지 | 🟡 MVP 개발용만 |
| FRED (미국 연준) | 무료 API 키 | ⏳ 약관 확인 필요 | Phase 11 |
| ClinicalTrials.gov | 미국 정부 데이터 | ✅ 자유 (예상) | ⏳ Phase 21 확인 |
| FDA openFDA | 미국 정부 데이터 | ✅ 자유 (예상) | ⏳ Phase 21 확인 |
| DART (한국 금감원) | 무료 API 키 | ⏳ 약관 확인 필요 | Phase 21 |
| 뉴스 웹사이트 크롤링 | ⚠️ 사이트별 ToS·robots.txt | ❌ 원문 저장/재배포 금지 | 🟡 **원문 전체 저장 금지, 인용+링크만** |

**뉴스 관련 중요 원칙 (Research Firewall 설계에 반영):**
- 기사 **전문(full text)을 우리 DB에 영구 저장하지 않는다.** 저작권 문제가 된다.
- 저장하는 것: URL, 제목, 발행일, 원문 소스, **추출된 사실(fact) + 짧은 인용**, content_hash.
- `robots.txt`를 존중한다.
- 이건 라이선스 문제이자 §22 Research Firewall의 설계 제약이다.

---

## 6. 최종 판정

| 질문 | 답 |
|---|---|
| **라이선스 위험이 있는가?** | **현재 계획대로면 없음.** RED 3건(OpenBB / vectorbt / nautilus_trader)을 모두 **코드에서 배제**했기 때문. |
| **가장 큰 위험은?** | OpenBB의 AGPL-3.0. 편리해 보여서 나중에 "그냥 이거 쓰자"가 되는 순간 전체 소스 공개 의무가 생길 수 있음. → **이 문서를 근거로 앞으로도 계속 거절할 것.** |
| **미해결 항목은?** | Redis 라이선스 재확인(Phase 5), lightweight-charts 귀속 표기 수용 여부(사용자 확인), FinGPT 베이스 모델(사용 시), 데이터 API 약관(Phase 11) |
| **상업화 가능한가?** | 현재 스택 기준 **가능.** GREEN 항목만으로 구성했고 모두 permissive다. 단 yfinance는 반드시 교체해야 함. |

---

## 7. Phase 4에서 만들 파일

- `C:\ai-research\THIRD_PARTY_LICENSES.md` — 사용하는 모든 의존성의 라이선스 전문 수집
- `C:\ai-research\NOTICE` — Apache-2.0 항목들의 NOTICE 통합
- `scripts\license-check.ps1` — `pip-licenses` + `license-checker`로 의존성 라이선스를 자동 스캔해 GPL/AGPL 계열이 몰래 끼어들었는지 검사 (CI에도 넣을 것)

> 마지막 항목이 중요합니다. **간접 의존성(transitive dependency)으로 AGPL 패키지가 들어오는 사고**가 실제로 자주 발생합니다. 사람이 매번 확인할 수 없으니 스크립트로 막습니다.
