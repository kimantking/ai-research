# GITHUB RESEARCH — AI STOCK RESEARCH OFFICE

- 조사일: **2026-09-02**
- 조사 도구: 웹 검색 + GitHub 저장소 페이지 직접 확인
- Research Depth: 10/10 (README + 라이선스 파일 + 유지보수 지표 확인)

> **정직성 고지**
> Star 수치는 조사일 기준 GitHub 페이지에서 읽은 값이며 반올림/근사치입니다.
> 별 개수는 품질 지표로 쓰지 않았고, **라이선스 · 최근 활동 · 아키텍처 적합성**을 기준으로 판단했습니다.
> "확인 못 함"으로 적힌 항목은 추측하지 않고 그대로 남겨두었습니다.

---

## 0. 결론 먼저 (요약표)

| Repo | 역할 | License | 채택 판단 |
|---|---|---|---|
| pixel-agents-hq/pixel-agents | Pixel Office UI 레퍼런스 | MIT | 🟢 **아키텍처 참고 + 스프라이트/레이아웃 아이디어** |
| Pixel-Process-UG/agent-office | Pixel Office UI 레퍼런스 | MIT | 🟢 참고 (규모 작음) |
| TauricResearch/TradingAgents | Agent 역할분리 설계 | Apache-2.0 | 🟢 **설계 참고 (코드 직접 병합 X)** |
| virattt/ai-hedge-fund | Agent 페르소나 설계 | MIT | 🟢 설계 참고 |
| microsoft/qlib | Quant 데이터/팩터/백테스트 | MIT | 🟡 **개념 참고 + 선택적 부분 의존** |
| AI4Finance-Foundation/FinGPT | 금융 NLP 개념 | MIT (코드) | 🟡 개념만. 모델/데이터셋은 별도 라이선스 |
| TA-Lib/ta-lib-python | 지표 계산 (고속) | BSD-2-Clause | 🟢 **직접 의존 (선택적 가속)** |
| xgboosted/pandas-ta-classic | 지표 계산 (순수 파이썬) | MIT | 🟢 **직접 의존 (기본)** |
| dgunning/edgartools | SEC EDGAR 접근 | MIT | 🟢 **직접 의존** |
| ranaroussi/quantstats | 성과 지표 | Apache-2.0 | 🟢 **직접 의존** |
| robertmartin8/PyPortfolioOpt | 포트폴리오 최적화 | MIT | 🟢 직접 의존 (후반 Phase) |
| gerrymanoim/exchange_calendars | 거래소 캘린더 | Apache-2.0 | 🟢 **직접 의존 (Point-in-Time 필수)** |
| langchain-ai/langgraph | Agent 오케스트레이션 | MIT | 🟢 **직접 의존** |
| BerriAI/litellm | LLM 공급자 추상화 + 비용추적 | MIT | 🟢 **직접 의존 (§51 모델 독립성 해결)** |
| tradingview/lightweight-charts | 프론트 차트 | Apache-2.0 (+귀속 의무) | 🟡 채택 가능하나 **TradingView 표기 의무** |
| matplotlib/mplfinance | 차트 PNG 렌더 (Agent 학습용) | Matplotlib License (BSD 계열) | 🟢 직접 의존 |
| pixijs/pixijs | 픽셀 렌더링 엔진 | MIT | 🟡 **MVP는 Canvas 2D, 필요시 승격** |
| QuantConnect/Lean | 백테스트 엔진 | Apache-2.0 | 🔴 **미채택 (C#/.NET, 과도한 복잡도)** |
| OpenBB-finance/OpenBB | 금융 데이터 플랫폼 | **AGPL-3.0** | 🔴 **코드 병합 금지. 아이디어만** |
| nautechsystems/nautilus_trader | 트레이딩 엔진 | **LGPL-3.0** | 🔴 현재 Phase 불필요 |
| polakowo/vectorbt | 벡터 백테스트 | Apache-2.0 **+ Commons Clause** | 🔴 **비오픈소스 조항. 미채택** |
| ranaroussi/yfinance | Yahoo 데이터 | Apache-2.0 (코드) | 🟡 **개발/MVP 전용. 데이터는 Yahoo 개인용 ToS** |

---

## 1. PIXEL / AGENT OFFICE 계열

### 1-1. `pixel-agents-hq/pixel-agents` — ⭐ 약 9.2k
- **무엇인가**: 터미널에서 돌아가는 AI 코딩 에이전트를 픽셀아트 캐릭터로 가상 사무실에 띄우는 도구.
- **기술 스택**: React 19 + Vite + **Canvas 2D**, 백엔드 Fastify(Node 20+), 테스트 Vitest/Playwright, 빌드 esbuild.
- **왜 좋은가**:
  - 우리가 원하는 UX와 가장 가깝다 (캐릭터 애니메이션이 에이전트 동작에 연동).
  - **"agent-agnostic / editor-agnostic"** 설계 — 즉 에이전트 상태를 외부에서 주입하는 경계가 이미 존재한다.
  - 이 계열 중 유일하게 커뮤니티 규모가 크다 (open issue 31, PR 53 → 살아있는 프로젝트).
- **가장 중요한 발견**: **PixiJS가 아니라 Canvas 2D로 충분하다**는 실증.
  9.2k 규모 프로젝트가 Canvas 2D만으로 픽셀 오피스를 굴리고 있다. 우리 MVP도 PixiJS 의존성을 처음부터 넣을 이유가 없다.
- **우리가 가져올 것**: 오피스 그리드 좌표계, 캐릭터 상태머신(idle/walking/working), 말풍선(speech bubble) UI 패턴, 스프라이트 시트 구성 방식.
- **가져오지 않을 것**: 코딩 에이전트 특화 로직(tmux/터미널 연결, VS Code 확장) 전부. 우리 도메인은 금융 리서치다.
- **직접 dependency 여부**: ❌ 아니오. **아키텍처 레퍼런스**로만 사용.
  이유 — 이 프로젝트는 "코딩 에이전트 모니터"이고 우리는 "리서치 조직 시뮬레이션"이라 데이터 모델이 근본적으로 다르다. 포크하면 남의 도메인 모델을 계속 걷어내야 한다.
- **License**: MIT (병합해도 법적 문제 없음. 병합하지 않는 건 순수 설계 판단)
- **통합 난이도**: 낮음 (참고만 하므로)
- **리스크**: 낮음

### 1-2. `Pixel-Process-UG/agent-office` — ⭐ 약 39
- **무엇인가**: "Pixel-art virtual office for AI agent teams". React + TypeScript + Vite / Node + Drizzle ORM / PostgreSQL 또는 SQLite / Docker.
- **좋은 점**: 스택이 우리가 쓰려는 것과 거의 동일(PostgreSQL, Docker, TS). Tiled map 기반 픽셀 맵.
- **한계**: **에이전트 상태 → 시각화 전송 프로토콜(WebSocket인지 폴링인지)이 문서화되어 있지 않다.** 확인 못 함. 규모도 작아 유지보수 지속성 불확실.
- **판단**: 🟡 Tiled 맵 구성 방식만 참고. 의존하지 않음.
- **License**: MIT

### 1-3. `fakeou/agent-office` (AgentOffice) — ⭐ 약 16
- **무엇인가**: Claude/Codex 등 터미널 코딩 에이전트용 local-first "office supervisor". Node 18+ / tmux / xterm.js / GDScript(Godot) 혼합, pnpm 모노레포. v0.1.9 (2026-03-24).
- **좋은 점**: 상태 모델이 명확 — `idle` / `working` / `approval` / `attention`. 우리 §42 상태 목록의 최소 골격으로 참고 가치.
- **한계**: 규모 매우 작음. GDScript(Godot) 혼합은 우리 웹 스택과 맞지 않음.
- **판단**: 🟡 상태 네이밍만 참고.
- **License**: MIT

### 1-4. 그 외 발견 (추가 후보, 미검증)
검색 중 아래 프로젝트들이 추가로 확인됨. **아직 개별 검증하지 않았으므로 채택 판단 보류.**
- `IvanWng97/pixtuoid` — 터미널 픽셀아트 오피스
- `jaffer1979/openclaw-pixel-agents-dashboard` — 스프라이트 + 활동 말풍선 + 하드웨어 모니터
- `liuyixin-louis/agentroom` — 프로젝트별 오피스 분리 개념 (우리 "부서(Department)" 개념과 유사 → 나중에 재조사 가치 있음)
- `Mgpixelart/pixel-agent-desk`

> 필요하면 Phase 7(Pixel Office MVP) 직전에 이 4개를 추가 정밀 조사하겠습니다.

### 1-5. 렌더링 엔진 결정: PixiJS vs Canvas 2D
| | PixiJS 8 | Canvas 2D |
|---|---|---|
| License | MIT | 브라우저 내장 |
| 번들 크기 | 큼 | 0 |
| WebGL/WebGPU | ✅ | ❌ |
| 스프라이트 수천 개 | 강함 | 수백 개까지는 충분 |
| 학습/디버깅 비용 | 높음 | 낮음 |

- 우리 MVP 동시 표시 캐릭터: **14명** (§62 초기 ACTIVE 팀).
- → **결정: MVP는 Canvas 2D.** 렌더러를 `OfficeRenderer` 인터페이스 뒤에 숨겨서, 캐릭터가 100명 넘어가고 프레임이 떨어지면 그때 PixiJS 구현체로 교체한다.
- 근거: §9 "복잡성을 위해 기술을 추가하지 마라". pixel-agents(9.2k)의 실증.

---

## 2. FINANCIAL MULTI-AGENT 계열

### 2-1. `TauricResearch/TradingAgents` — ⭐ 매우 큼 (조사일 기준 GitHub 표기 98k 수준)
- **무엇인가**: LangGraph 기반 멀티에이전트 금융 트레이딩 프레임워크. 논문 arXiv:2412.20138.
- **정의된 역할**: Fundamentals Analyst / Sentiment Analyst / News Analyst / Technical Analyst / Bullish Researcher / Bearish Researcher / Trader / Risk Management Team / Portfolio Manager.
- **유지보수**: 활발. v0.3.1 (2026-07), 커밋 257개, LLM 공급자 확장 중.
- **왜 좋은가**: **Bull/Bear를 독립 에이전트로 분리하고 Research Manager가 중재하는 구조**가 우리 §12·§15·§17과 정확히 일치. 이 설계는 검증된 것으로 봐도 좋다.
- **우리가 가져올 것 (설계만)**:
  1. Analyst층 → Researcher(Bull/Bear)층 → Manager층 → Risk층의 **4단 파이프라인**
  2. LangGraph **stateful graph + 조건부 엣지**로 토론 라운드를 반복시키는 패턴
  3. 토론 종료 조건(round limit + judge 판정) 패턴
- **가져오지 않을 것**:
  - **Trader / 실제 주문 관련 전부** (§5에 따라 우리는 실거래 미구현)
  - 이 프로젝트의 데이터 접근 계층 (Point-in-Time 보장이 우리 기준에 못 미침 — 우리 §20이 훨씬 엄격하다)
  - 프롬프트 그대로 복사 (우리는 §25 NO EVIDENCE POLICY를 프롬프트에 강제해야 함)
- **직접 dependency 여부**: ❌ 아니오. Apache-2.0이라 병합해도 합법이지만, **우리 Evidence Graph / Point-in-Time / Research Firewall 요구사항이 이 프로젝트에 없다.** 껍데기를 가져오면 그 세 가지를 다시 뜯어 넣어야 해서 이득이 없다.
- **License**: Apache-2.0 (🟢 상업 이용 가능, 수정 가능, NOTICE 유지 필요)
- **리스크**: 논문 프로젝트 특유의 "성능 주장"을 그대로 믿지 말 것. 백테스트 결과는 우리가 §19~20 기준으로 다시 검증해야 함.

### 2-2. `virattt/ai-hedge-fund` — ⭐ 약 63.1k
- **무엇인가**: 투자 대가 페르소나를 pluggable "alpha model"로 만든 AI 헤지펀드 PoC. Python + Poetry, Anthropic/OpenAI/DeepSeek/Google/xAI/Kimi 지원.
- **좋은 점**: **"에이전트 = 교체 가능한 플러그인"** 이라는 레지스트리 개념. 우리 §11 Agent Registry와 직결.
- **중요**: 저자 스스로 **"교육/연구 목적이며 실거래용 아님, 실제 주문 안 함"**을 명시. 우리 §5와 동일한 자세 → 참고할 만한 태도.
- **한계**: 데이터는 유료 `Financial Datasets API`에 묶여 있음 → 우리 §55(무료 우선)와 충돌. 데이터 계층은 안 가져온다.
- **판단**: 🟢 Agent Registry / 페르소나 플러그인 패턴만 설계 참고.
- **License**: MIT

---

## 3. QUANT / ML 계열

### 3-1. `microsoft/qlib` — ⭐ 약 47.4k, MIT
- **구성**: Data Layer(Alpha158/Alpha360 팩터셋, 표현식 캐시), Model Zoo(LightGBM~Transformer 20종+), Backtest(nested decision execution), Python 3.8~3.12 지원.
- **왜 중요한가**: 우리 §18 데이터 파이프라인과 §39 Pattern Miner를 **처음부터 새로 발명하지 않아도 되는 참고 설계**를 제공한다. 특히 **expression-based feature engineering**(`"Ref($close,-1)/$close-1"` 같은 식으로 팩터를 문자열로 정의)은 Pattern Miner의 조건 표현에 그대로 쓸 만하다.
- **주의점 (정직하게)**: 최신 정식 릴리스 태그가 **v0.9.0 (2022-12-09)** 로 표기됨. 커밋은 이후에도 있으나, **"릴리스가 오래된 프로젝트"**라는 점은 리스크로 기록한다. 또한 중국/미국 시장 데이터 워크플로에 최적화되어 있어 한국·대만·스웨덴 시장에는 그대로 맞지 않는다.
- **판단**: 🟡 **Phase 20(Pattern Miner) 전까지는 의존하지 않는다.** 그 전까지는 개념 참고. 필요해지면 `qlib`의 데이터 핸들러만 선택적으로 도입 검토.
- **License**: MIT 🟢

### 3-2. `AI4Finance-Foundation/FinGPT` — ⭐ 약 20.5k, MIT
- **제공물**: 금융 감성분석 LLM(FinGPT v3), FinGPT-Forecaster, 데이터셋(fingpt-sentiment-train 76.8K행 등), LoRA 파인튜닝 노트북, RAG 프레임워크.
- **⚠️ 라이선스 함정**: **저장소 코드가 MIT라고 해서 모델 가중치와 데이터셋까지 MIT는 아니다.** 베이스 모델이 Llama2/Falcon/Bloom/ChatGLM2/Qwen이며 각각 별도 라이선스(Llama2 Community License 등)를 따른다. HuggingFace 데이터셋도 별도 조건이 있다.
- **판단**: 🟡 **개념만 참고.** 금융 감성분석은 초기에는 우리 LLM 라우터로 처리하고, 자체 모델 파인튜닝은 Phase 21 이후로 미룬다.
- **리스크**: 실제로 모델을 쓰게 되면 **베이스 모델 라이선스를 그때 다시 감사해야 한다** (LICENSE_AUDIT.md에 미해결 항목으로 기록).

---

## 4. TECHNICAL ANALYSIS 계열

### 4-1. `TA-Lib/ta-lib-python` — ⭐ 약 12.1k, **BSD-2-Clause** 🟢
- C로 작성된 TA-Lib의 파이썬 래퍼. 150여 지표 + 캔들패턴.
- **Windows 관련 좋은 소식**: 조사 시점 기준 **Python 3.9~3.14용 Windows x86_64 prebuilt wheel 제공**. 즉 과거처럼 C 라이브러리를 직접 컴파일할 필요 없이 `pip install TA-Lib`로 끝날 가능성이 높다.
- **단, 실패 대비 필수**: wheel이 안 맞으면 Windows에서 빌드 지옥이 열린다. → **TA-Lib은 "선택적 가속기"로만 쓰고, 없어도 시스템이 돌아가야 한다.**
- **판단**: 🟢 optional dependency.

### 4-2. `xgboosted/pandas-ta-classic` — ⭐ 약 356, MIT 🟢
- 192개 지표 + 62개 네이티브 캔들패턴 = 252개. **TA-Lib 없이도 순수 파이썬으로 동작**(34개 핵심 지표는 TA-Lib 있으면 가속).
- 릴리스 **0.6.20 (2026-05-20)**, 커밋 1,015 → 살아있음.
- 원조 `twopirllc/pandas-ta`가 정체된 뒤 커뮤니티가 이어받은 포크 계열.
- **판단**: 🟢 **기본 지표 엔진으로 직접 채택.** 별 개수는 적지만 우리 요구(§14 지표 목록 전부 커버 + Windows에서 무조건 설치됨)를 정확히 만족한다. → **별 개수로 판단하지 않는다는 §8 원칙의 실제 적용 사례.**

### 4-3. `matplotlib/mplfinance` — ⭐ 약 4.4k
- 캔들차트 + 볼륨 + 이동평균 오버레이를 **PNG로 렌더링** 가능. `mpf.plot(daily, type='candle', mav=(3,6,9), volume=True)`
- **왜 필요한가**: §38 "차트 이미지 + 수치 데이터 동시 제공" — Agent에게 실제 차트 그림을 보여주려면 서버에서 이미지를 만들어야 한다. 프론트엔드 차트로는 불가능하다.
- **License**: Matplotlib License (BSD 계열 permissive) 🟢

### 4-4. `tradingview/lightweight-charts` — ⭐ 약 17.2k, Apache-2.0
- **⚠️ 조건부**: 라이선스가 **TradingView 귀속 표기를 요구**한다. NOTICE 파일의 attribution notice와 tradingview.com 링크를 사용자에게 보이는 페이지에 넣어야 하고, `attributionLogo` 옵션 사용을 권장한다.
- **판단**: 🟡 채택 가능. 단 **UI에 TradingView 표기가 들어간다는 것을 사용자가 수용해야 한다.** 원하지 않으면 대안은 `uPlot`(MIT) 또는 자체 Canvas 차트.
- → DECISIONS.md에 "사용자 확인 필요 항목"으로 기록.

---

## 5. SEC / 데이터 소스

### 5-1. `dgunning/edgartools` — ⭐ 약 2.6k, **MIT** 🟢
- 10-K / 10-Q / 8-K / 13F / Form 3·4·5 / XBRL / Schedule 13D·G / DEF 14A / S-1 / Form 144 등 폭넓게 커버. 1994년부터의 전체 filing history 접근.
- Company Facts API 기반 시계열 조회 지원 → **Point-in-Time 쿼리의 재료**를 제공.
- **판단**: 🟢 **직접 채택.** SEC 접근을 직접 구현할 이유가 없다.
- **단, 우리가 추가해야 할 것**: edgartools는 데이터를 가져다줄 뿐, **§20 look-ahead bias 차단은 우리 책임**이다. `filing_date`(공시 시점)와 `period_of_report`(대상 기간)를 반드시 분리 저장하고, 백테스트 시엔 `filing_date <= T` 필터를 우리 쿼리 계층에서 강제해야 한다.

### 5-2. SEC EDGAR 공식 API (1차 소스)
공식 웹마스터 FAQ에서 직접 확인한 사실:
- **요청 한도: 초당 10 requests** ("carefully monitored to preserve equitable access")
- **필수 헤더**: `User-Agent: <회사/이름> <연락 이메일>`, `Accept-Encoding: gzip, deflate`
  → 없으면 "Undeclared Automated Tool" 오류
- **데이터 이용**: "All Government-created content on sec.gov and EDGAR public filing content are **free to access and reuse**" — 재배포 제한 없음. **Tier S 소스로 최우선 채택.**

### 5-3. `gerrymanoim/exchange_calendars` — ⭐ 약 635, Apache-2.0 🟢
- 50개 이상 거래소 캘린더. **NYSE(XNYS), NASDAQ, KRX(XKRX), TWSE(XTAI) 모두 포함** ← antking님의 관심 시장(한국·미국·대만)을 전부 커버.
- **왜 필수인가**: §20 Point-in-Time의 기초. "T 시점에 시장이 열려 있었는가", "T+5D는 실제로 며칠 뒤인가"를 정확히 계산하지 못하면 백테스트 전체가 틀어진다. 이건 직접 구현하면 반드시 버그가 난다.
- **판단**: 🟢 **직접 채택 (필수)**

### 5-4. `ranaroussi/yfinance` — ⭐ 약 25k, 코드 Apache-2.0
- **⚠️ 데이터 이용 조건 주의**: README가 명시 — 이 도구는 "research and educational purposes" 용이며 **"the Yahoo! finance API is intended for personal use only"**. yfinance 자체는 Yahoo와 무관하며 사용자가 Yahoo ToS를 확인할 책임이 있다.
- **판단**: 🟡 **개발·MVP 단계 전용.** Provider 인터페이스 뒤에 두고, 공개 배포나 상업화 시점에는 정식 라이선스 데이터로 교체할 수 있게 설계한다. 코드가 yfinance에 직접 묶이면 안 된다.
- → §21 "Provider interface를 추상화한다"가 바로 이 문제 때문에 필요하다.

### 5-5. 유료/무료 데이터 API 조사 (Phase 11에서 결정)
Alpha Vantage / Tiingo / Polygon / EODHD / Financial Modeling Prep 비교 자료는 확보했으나, **각 서비스의 무료 티어 한도와 재배포 조항은 서비스 약관이 자주 바뀌므로 Phase 11 착수 시점에 다시 확인**하겠습니다. 지금 숫자를 적어두면 틀린 정보가 됩니다. (§66 "출처 없는 숫자 생성" 금지 적용)

MVP 데이터 전략은 **비용 0원**으로 간다:
1. SEC EDGAR (공식, 무료, 재배포 자유) — Tier S
2. exchange_calendars (거래일)
3. yfinance (OHLCV, 개발용)
4. FRED (거시경제, 무료 API 키) — Phase 11에서 검증

---

## 6. 백테스트 / 포트폴리오 / 리스크

### 6-1. `ranaroussi/quantstats` — ⭐ 약 7.5k, **Apache-2.0** 🟢
- Sharpe / Sortino / Max Drawdown / Calmar / 변동성 / Monte Carlo / HTML tear sheet. Python 3.10+.
- 커밋 592, 이슈 11, PR 19 → 활동 있음.
- **판단**: 🟢 **직접 채택.** §36 Agent Performance 지표를 직접 구현하지 않고 이걸로 계산한다.

### 6-2. `robertmartin8/PyPortfolioOpt` — ⭐ 약 6k, **MIT** 🟢
- Mean-Variance, Black-Litterman, HRP, mean-CVaR, Ledoit-Wolf 수축추정, 이산 배분(discrete allocation).
- 유지보수 중단 공지 없음, 커밋 865.
- **판단**: 🟢 채택. 단 **Phase 19 이후**. MVP에 포트폴리오 최적화는 필요 없다.

### 6-3. `QuantConnect/Lean` — ⭐ 약 21.2k, Apache-2.0
- 이벤트 드리븐 백테스트/라이브 엔진. **주 언어 C# (.NET)**, 커밋 13,294.
- **판단**: 🔴 **미채택.**
  - 이유 1: C#/.NET 런타임을 Python 백엔드 옆에 하나 더 띄워야 한다 → 초보 사용자 기준 운영 복잡도 폭증.
  - 이유 2: LEAN의 강점은 **실거래 연동**인데 우리는 §5에서 실거래를 명시적으로 제외했다.
  - 이유 3: 우리에게 필요한 건 "이벤트 드리븐 엔진"이 아니라 **"look-ahead bias가 없는 리서치 재현 엔진"**이다. 이건 우리 데이터 계층 문제지 엔진 문제가 아니다.
  - 라이선스는 문제없음(Apache-2.0). **순수하게 복잡도 판단으로 제외.**
- **가져올 아이디어**: 데이터 정규화 계층, 슬리피지/수수료 모델링, 시간축을 엔진이 전진시키고 전략은 "현재 시점까지만" 볼 수 있게 하는 구조. → 우리 백테스트 엔진을 훨씬 작게 직접 구현할 때 이 개념을 따른다.

### 6-4. `polakowo/vectorbt` — ⭐ 약 8.7k
- **🔴 라이선스 결격**: **Apache-2.0 + Commons Clause**. Commons Clause는 "이 소프트웨어에 실질적으로 기반한 제품/서비스 판매"를 금지한다. **이건 OSI 승인 오픈소스가 아니다.** 오픈소스판은 상용 vectorbt PRO의 커뮤니티 에디션이다.
- **판단**: 🔴 **미채택.** antking님이 나중에 이 시스템을 제품화할 가능성이 조금이라도 있으면 지금 넣으면 안 된다. 나중에 걷어내는 비용이 훨씬 크다.

### 6-5. `nautechsystems/nautilus_trader` — ⭐ 약 24.1k
- Rust 기반 나노초 해상도 트레이딩 엔진. Rust 71% / Python 22.5%.
- **🔴 라이선스 주의: LGPL-3.0.** 파이썬에서 import 하는 경우 "동적 링크"로 볼 수 있는지가 법적으로 회색지대다. LGPL은 라이브러리 자체를 수정하면 그 부분을 공개해야 한다.
- **판단**: 🔴 **현재 미채택.** 기술적으로는 훌륭하지만 우리는 실거래를 안 하므로 이 엔진의 핵심 가치(라이브 실행)를 쓸 일이 없다. 복잡도만 늘어난다.

---

## 7. OPENBB — 반드시 읽어야 할 라이선스 경고

### `OpenBB-finance/OpenBB`
**LICENSE 파일을 직접 확인한 결과: GNU Affero General Public License v3.0 (AGPL-3.0), Copyright (c) 2021-2025 OpenBB Inc.**

AGPL-3.0의 핵심 (Section 13, 네트워크 조항):
> 프로그램을 수정하고 사용자가 **네트워크를 통해 원격으로 상호작용**하게 하면, 그 사용자들에게 **수정된 버전의 전체 소스코드를 제공할 기회를 명시적으로 제공해야 한다.**

**우리 프로젝트에 미치는 실제 영향**:
- 이 시스템은 웹 대시보드(Next.js + FastAPI)다. 즉 **네트워크로 접근하는 서비스**다.
- OpenBB 코드를 우리 백엔드에 병합하면 → **우리 시스템 전체 소스를 사용자에게 공개해야 할 의무가 생길 수 있다.**
- 일반 GPL보다 강하다. GPL은 배포할 때만 걸리지만, AGPL은 **웹서비스로 제공만 해도** 걸린다.

**판단: 🔴 RED — 코드 직접 병합 절대 금지.**

허용되는 사용:
1. **아키텍처 참고** — OpenBB의 provider/standardization 패턴은 우리 §21 Provider 추상화 설계에 좋은 참고자료다. **읽고 배우는 것은 라이선스 위반이 아니다.**
2. **완전히 분리된 선택적 외부 서비스**로만 사용 (별도 프로세스, 별도 컨테이너, HTTP로만 통신, 우리 코드와 링크되지 않음) — 그래도 법적 리스크가 남으므로 MVP에서는 아예 쓰지 않는다.

---

## 8. 우리가 추가로 제안하는 기술 (사용자 목록에 없던 것)

§69 "발견한 더 좋은 기술이 있으면 추가 제안하라"에 따른 제안. 각각 **왜 필요한지 / 무엇을 대체하는지 / 라이선스 / 유지보수 / 통합 가치**를 명시합니다.

### 8-1. `BerriAI/litellm` — ⭐ 약 53.8k, MIT 🟢 **강력 추천**
- **무엇인가**: 100개 이상 LLM API를 OpenAI 포맷으로 통일해서 호출하는 Python SDK + 프록시 서버(AI Gateway). **비용 추적(cost tracking), 로드밸런싱, 가드레일, 예산 한도, 가상 키** 내장.
- **왜 필요한가**: 우리 요구사항 **§51(모델 독립성), §52(모델 라우팅), §54(비용 제어)를 한 번에 해결한다.**
  - §51: Claude / OpenAI / Gemini / local model 교체 가능 → LiteLLM이 정확히 이걸 한다.
  - §54: "Agent별 tokens / calls / provider / estimated cost / daily cost 추적" → LiteLLM이 이미 구현해 놓은 기능이다. 우리가 직접 만들면 각 공급자의 토큰 가격표를 계속 따라다녀야 한다.
- **무엇을 대체하는가**: 우리가 직접 만들려던 `LLMProvider` 추상화 계층 + 비용 계산기.
- **License**: MIT 🟢 / **유지보수**: 매우 활발
- **통합 가치**: 높음. **채택 권장.**
- **주의**: 그래도 우리 코드는 LiteLLM에 직접 묶이지 않고 **얇은 `llm_gateway` 인터페이스**를 한 겹 더 둔다. LiteLLM 자체를 나중에 교체할 수 있어야 한다.

### 8-2. DuckDB (MIT) + Parquet — **Point-in-Time 저장소로 추천**
- **왜 필요한가**: §20 Point-in-Time Integrity의 실무적 해법. 시계열 스냅샷을 파티션된 Parquet로 저장하고 DuckDB로 `WHERE observed_at <= T` 쿼리를 거는 방식은 look-ahead bias를 **물리적으로** 차단하는 가장 단순한 구조다.
- **무엇을 대체하는가**: PostgreSQL을 대체하지 않는다. **보완한다.** PostgreSQL은 에이전트 상태·지식·감사로그(트랜잭션 필요), DuckDB/Parquet은 대용량 OHLCV·팩터(분석 쿼리).
- **License**: MIT 🟢
- **통합 가치**: 중간~높음. **Phase 11에서 도입 검토.** MVP에서는 PostgreSQL만으로 시작.

### 8-3. Pandera 또는 Great Expectations — 데이터 검증
- **왜 필요한가**: §18의 VALIDATION 단계, §57의 "Data Validation Tests"를 직접 `if` 문으로 짜면 유지가 안 된다. 스키마 기반 검증이 필요하다.
- **추천**: **Pandera** (MIT, 가벼움, pandas/polars 네이티브). Great Expectations는 강력하지만 MVP엔 과함.
- **통합 가치**: 중간. Phase 11에서 도입.

### 8-4. `arq` 또는 `dramatiq` — Job Queue
- **왜 필요한가**: §9의 "Background Job Queue". Celery는 **Windows 지원이 공식적으로 중단**되어 있어(Docker 안에서 돌리면 되지만 디버깅이 괴롭다) 초보자 친화적이지 않다.
- **추천**: **arq** (MIT, Redis 기반, asyncio 네이티브, FastAPI와 궁합 좋음, 매우 작음).
- **통합 가치**: 높음. Phase 5에서 도입.

### 8-5. `uv` (Astral, MIT/Apache-2.0) — Python 패키지 관리
- **왜 필요한가**: pip보다 10~100배 빠르고, `pyproject.toml` + `uv.lock`으로 **재현 가능한 잠금**을 제공한다. §2의 "명확한 requirements lock 방식"을 정확히 만족.
- **무엇을 대체하는가**: pip + pip-tools, 또는 Poetry.
- **주의**: 전역 설치가 필요하다(`pip install uv` 또는 standalone). **선택 사항으로 두고, 없으면 pip으로도 동작하게 한다.** 사용자 PC 전역을 함부로 바꾸지 않는다는 §0 원칙 준수.
- **통합 가치**: 중간. 있으면 좋고 없어도 됨.

### 8-6. `Playwright` (Apache-2.0) — Research Firewall 보조
- **왜 필요한가**: §22 Research Firewall에서 "가짜 스크린샷", "SEO 스팸" 같은 걸 걸러내려면 실제 페이지를 렌더링해야 하는 경우가 있다. 또 §57 "UI basic tests"에도 필요.
- **통합 가치**: 중간. Phase 13 / Phase 22.

### 8-7. `trafilatura` (Apache-2.0) — 본문 추출
- **왜 필요한가**: §22~23. 뉴스 페이지에서 **광고·내비게이션을 걷어낸 본문만** 추출하고, **원문 URL/카노니컬 링크·발행일**을 뽑아내야 중복 판정(§23 Source Lineage)이 가능하다. HTML을 통째로 LLM에 넣는 건 비용 낭비이자 스팸 유입 경로다.
- **대안**: `readability-lxml`(Apache-2.0). trafilatura가 메타데이터 추출이 더 강함.
- **통합 가치**: **높음.** Phase 13 핵심 부품.

### 8-8. `simhash` / MinHash (datasketch, MIT) — 중복 탐지
- **왜 필요한가**: §23 "같은 Reuters 원문을 50개 사이트가 복사한 것을 50개 독립 소스로 세면 안 된다". 정확 일치 해시(content_hash)만으로는 잡히지 않는다 — 사이트마다 문단 하나씩 다르다. **근사 중복(near-duplicate) 탐지**가 필요하다.
- **추천**: `datasketch`(MinHash LSH, MIT) 또는 simhash 직접 구현(간단함).
- **통합 가치**: **높음.** Phase 13 핵심 부품. 이게 없으면 §23이 구현 불가능하다.

---

## 9. Star 수로 판단하지 않은 사례 (§8 원칙 적용 기록)

| 사례 | Star | 그럼에도 채택 / 거절한 이유 |
|---|---|---|
| pandas-ta-classic | 356 | **채택.** 라이선스 MIT, 2026-05 릴리스, Windows에서 무조건 설치됨, 252개 지표로 §14 전부 커버. 별 개수보다 "지금 우리 환경에서 작동하는가"가 중요. |
| vectorbt | 8.7k | **거절.** Commons Clause 때문. 별 개수와 무관하게 상업적 사용 제약이 있다. |
| ai-hedge-fund | 63.1k | **의존 안 함.** 별은 많지만 유료 데이터 API에 묶여 있어 §55(무료 우선)와 충돌. 설계만 참고. |
| qlib | 47.4k | **보류.** 별은 많지만 정식 릴리스가 2022년으로 표기됨. 리스크로 기록하고 필요 시점에 재평가. |
| exchange_calendars | 635 | **필수 채택.** 별은 적지만 Point-in-Time의 토대. 직접 구현하면 반드시 틀린다. |

---

## 10. 미해결 / 추가 조사 필요 항목

| # | 항목 | 언제 |
|---|---|---|
| 1 | pixtuoid / openclaw-pixel-agents-dashboard / agentroom / pixel-agent-desk 정밀 조사 | Phase 7 직전 |
| 2 | FinGPT 사용 시 베이스 모델(Llama2 등) 라이선스 재감사 | 실제 사용 결정 시 |
| 3 | Alpha Vantage / Tiingo / Polygon / EODHD / FMP 무료 티어 한도 및 재배포 조항 | Phase 11 착수 시 |
| 4 | FRED API 이용 약관 확인 | Phase 11 |
| 5 | TA-Lib Windows wheel이 실제 antking님 환경에서 설치되는지 실증 | Phase 16 |
| 6 | lightweight-charts의 TradingView 귀속 표기를 UI에 넣을지 사용자 확정 | Phase 6 |
| 7 | 한국(KRX/DART)·대만(TWSE/TPEX)·스웨덴 데이터 소스 조사 — antking님 실제 관심 시장 | Phase 21 |

> **7번은 중요합니다.** 조사한 오픈소스 대부분이 미국 시장 중심입니다. antking님이 실제로 보는 종목(FOCI, EZconn, SIVE, 박셀바이오 등)은 TPEX/Spotlight/KOSDAQ에 있어서, MVP는 미국 시장으로 시작하되 **Provider 인터페이스를 처음부터 다중 시장 대응으로 설계**해야 합니다.

---

## Sources

- [pixel-agents-hq/pixel-agents](https://github.com/pixel-agents-hq/pixel-agents)
- [Pixel-Process-UG/agent-office](https://github.com/Pixel-Process-UG/agent-office)
- [fakeou/agent-office](https://github.com/fakeou/agent-office)
- [IvanWng97/pixtuoid](https://github.com/IvanWng97/pixtuoid)
- [jaffer1979/openclaw-pixel-agents-dashboard](https://github.com/jaffer1979/openclaw-pixel-agents-dashboard)
- [liuyixin-louis/agentroom](https://github.com/liuyixin-louis/agentroom)
- [Mgpixelart/pixel-agent-desk](https://github.com/Mgpixelart/pixel-agent-desk)
- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- [TradingAgents 논문 (arXiv:2412.20138)](https://arxiv.org/pdf/2412.20138)
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- [microsoft/qlib](https://github.com/microsoft/qlib)
- [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)
- [TA-Lib/ta-lib-python](https://github.com/TA-Lib/ta-lib-python)
- [xgboosted/pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic)
- [matplotlib/mplfinance](https://github.com/matplotlib/mplfinance)
- [matplotlib/mplfinance LICENSE](https://github.com/matplotlib/mplfinance/blob/master/LICENSE)
- [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts)
- [pixijs/pixijs](https://github.com/pixijs/pixijs)
- [dgunning/edgartools](https://github.com/dgunning/edgartools)
- [SEC Webmaster FAQ (EDGAR 자동 접근 규칙)](https://www.sec.gov/os/webmaster-faq)
- [gerrymanoim/exchange_calendars](https://github.com/gerrymanoim/exchange_calendars)
- [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance)
- [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats)
- [robertmartin8/PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt)
- [QuantConnect/Lean](https://github.com/QuantConnect/Lean)
- [polakowo/vectorbt](https://github.com/polakowo/vectorbt)
- [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader)
- [OpenBB LICENSE (AGPL-3.0 원문)](https://github.com/OpenBB-finance/OpenBB/blob/develop/LICENSE)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [BerriAI/litellm](https://github.com/BerriAI/litellm)
- [LLMQuant/awesome-trading-agents](https://github.com/LLMQuant/awesome-trading-agents)
- [georgezouq/awesome-ai-in-finance](https://github.com/georgezouq/awesome-ai-in-finance)
