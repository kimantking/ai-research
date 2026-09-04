# DATA SOURCES

> 유료 API 는 **사용자 승인 없이 가입하지 않습니다.**
> 무료·공식 소스를 먼저 구축하고, Provider 인터페이스로 추상화합니다.

---

## 1. 현재 연결 상태

| 공급자 | 상태 | 종류 | 비고 |
|---|---|---|---|
| **합성 캔들 생성기** | 🟢 CONNECTED | OHLCV | **실제 시장 데이터가 아닙니다.** 시드 고정 재현 가능 |
| SEC EDGAR | ⚪ DISCONNECTED | 공시 | Phase 12 |
| yfinance | ⚪ DISCONNECTED | OHLCV | Phase 11 |
| FRED | ⚪ DISCONNECTED | 거시 | Phase 11 |

Data 화면에서 실시간으로 확인할 수 있습니다.
**연결되지 않은 것은 연결되지 않았다고 표시합니다.**

---

## 2. Tier S — 공식 소스 (최우선)

### SEC EDGAR ✅ 무료 · 재배포 자유

SEC 웹마스터 FAQ에서 직접 확인한 사실:

- **요청 한도: 초당 10 requests**
- **필수 헤더**: `User-Agent: <이름/회사> <연락 이메일>`, `Accept-Encoding: gzip, deflate`
  없으면 "Undeclared Automated Tool" 오류로 차단
- **이용**: "All Government-created content on sec.gov and EDGAR public filing content
  are free to access and reuse" — **재배포 제한 없음**

`.env` 의 `SEC_USER_AGENT` 에 연락처를 반드시 넣어야 합니다.

커버 범위 (edgartools 경유): 10-K, 10-Q, 8-K, 13F, Form 3/4/5, XBRL,
Schedule 13D/G, DEF 14A, S-1, Form 144 — 1994년부터

**우리가 추가로 해야 할 것**: edgartools 는 데이터를 가져다줄 뿐입니다.
`filing_date`(공시 시점)와 `period_of_report`(대상 기간)를 **분리 저장**하고,
백테스트에서 `filing_date <= T` 필터를 우리 쿼리 계층에서 강제해야 합니다.

### 기타 Tier S (Phase 21)
FDA openFDA · ClinicalTrials.gov · USAspending(정부계약) ·
DART(한국) · KRX · TWSE/TPEX(대만)

---

## 3. 시세 (OHLCV)

### yfinance — ⚠️ 개발용만

- **코드 라이선스**: Apache-2.0 🟢
- **데이터 이용 조건**: README 명시 — "the Yahoo! finance API is
  **intended for personal use only**". yfinance 는 Yahoo 와 무관하며
  사용자가 Yahoo ToS 를 확인할 책임이 있습니다.

| 용도 | 가능? |
|---|---|
| 개인 연구 / 로컬 개발 | ✅ |
| 공개 서비스 / 상업 배포 / 데이터 재배포 | ❌ |

→ 반드시 **Provider 인터페이스 뒤**에 두고 교체 가능하게 설계합니다.

### 유료 대안 (Phase 21에서 사용자 승인 후 검토)

Alpha Vantage / Tiingo / Polygon / EODHD / Financial Modeling Prep

> 각 서비스의 무료 티어 한도와 재배포 조항은 **자주 바뀝니다.**
> 지금 숫자를 적어두면 틀린 정보가 됩니다. Phase 21 착수 시점에 다시 확인합니다.

---

## 4. 거래 캘린더 — 필수

`exchange_calendars` (Apache-2.0, 50개 이상 거래소)

**NYSE(XNYS) · NASDAQ · KRX(XKRX) · TWSE(XTAI) 전부 포함** —
antking님의 관심 시장(한국·미국·대만)을 커버합니다.

### 왜 필수인가

"T+5D" 는 **달력 5일이 아니라 거래일 5일**이며 거래소마다 다릅니다.
휴장일을 잘못 계산하면 백테스트 전체가 틀어집니다.
직접 구현하면 반드시 버그가 납니다.

---

## 5. 뉴스 — 저작권 제약

| 하는 것 | 안 하는 것 |
|---|---|
| URL, 제목, 발행일 저장 | **기사 전문 영구 저장** |
| 원문 소스 추적 | 원문 재배포 |
| 추출된 사실 + 짧은 인용 | 전문 복사 |
| `robots.txt` 존중 | 무시 |

우리가 원하는 건 기사가 아니라 **검증된 사실**입니다.

---

## 6. Phase 21 확장 예정

Company IR · 어닝콜 · 거시경제 · 섹터 데이터 · 정부계약 ·
기관보유(13F) · 내부자거래(Form 4) · 공매도 잔고 · 옵션 · ETF 자금흐름

---

## 7. Provider 인터페이스 설계

```python
class MarketDataProvider(Protocol):
    def get_bars(self, symbol: str, tf: str,
                 start: datetime, end: datetime) -> OHLCV: ...
    def status(self) -> ProviderStatus: ...   # CONNECTED/DISCONNECTED/ERROR/STALE/RATE_LIMITED
```

구현체를 갈아끼워도 **위 계층은 전혀 바뀌지 않습니다.**
`.env` 의 `MARKET_DATA_PROVIDER` 로 선택합니다 (`mock` | `yfinance` | ...).

---

## 8. 우선순위 (antking님 관심 시장 반영)

조사한 오픈소스는 대부분 **미국 시장 중심**입니다.
antking님이 실제로 보시는 종목(FOCI, EZconn, SIVE, 박셀바이오 등)은
TPEX / Spotlight / KOSDAQ 에 있습니다.

→ MVP 는 미국 시장으로 시작하되, **Provider 인터페이스를 처음부터
다중 시장 대응으로 설계**했습니다. Phase 21 에서 DART / TWSE / TPEX 를 추가합니다.
