# CHART ENGINE

구현: `packages/chart_skills/`
테스트: `tests/test_indicators.py` (24개)

---

## 1. 원칙: 모든 에이전트가 차트를 본다

차트 분석을 Technical Master 한 명에게 맡기지 않습니다.
**모든 Sector Lead / Bull / Bear 가 `common_chart_skill` 을 기본 장착**합니다.

`tests/test_registry_and_engine.py::test_all_sector_agents_have_common_chart_skill`
이 이걸 강제합니다.

---

## 2. 공통 차트 스킬

### 지표 (전부 순수 파이썬 구현, 의존성 0)

| 분류 | 지표 |
|---|---|
| 이동평균 | SMA, EMA, VWAP (누적/앵커) |
| 모멘텀 | RSI(Wilder), MACD, ROC, Stochastic |
| 변동성 | ATR(Wilder), Bollinger Bands, True Range |
| 추세 | ADX (+DI/-DI) |
| 거래량 | OBV, RVOL, Relative Strength |

### ★ None 을 0 으로 채우지 않습니다

```python
sma([1,2,3], 5)   # → [None, None, None]   (0.0 이 아님)
```

"아직 모른다"와 "값이 0이다"는 완전히 다릅니다.
0으로 채우면 백테스트가 **조용히** 틀립니다. 테스트가 이걸 감시합니다.

### 시장 구조

HH / HL / LH / LL, 지지·저항, 추세·레인지, 돌파·실패돌파, 갭,
변동성 확장·수축, 모멘텀 다이버전스

```python
market_structure(series)
# {
#   "trend": "uptrend",
#   "structure": {"HH": true, "HL": true, "LH": false, "LL": false},
#   "support": 96.2, "resistance": 118.4,
#   "breakout": false, "rsi14": 58.3, "adx14": 27.1, "rvol20": 1.12,
#   "disclaimer": "기술적 신호는 통계적 경향이며 확정된 예측이 아닙니다."
# }
```

**disclaimer 는 항상 붙습니다.** 패턴 이름을 물리 법칙처럼 다루지 않기 위해서입니다.

---

## 3. 멀티 타임프레임

```python
daily = series
weekly = series.resample(5)     # 5봉 묶기
monthly = series.resample(21)
```

`resample()` 은 **미완성 묶음을 버립니다.** 진행 중인 주봉을 완성된 것처럼
쓰면 그 자체가 미래 정보 사용입니다.

지원 계획: Monthly / Weekly / Daily / 4H / 1H / 30M / 15M / 5M / 1M
상위 → 하위 순으로 종합합니다.

```
Weekly Trend  →  Daily Structure  →  4H Setup  →  1H Momentum  →  15M Trigger
```

---

## 4. 섹터별 차트 스킬

`config/agents/*.yaml` 의 `skills` 로 지정합니다.

| 섹터 | 스킬 |
|---|---|
| Biotech / Pharma | `sector_chart_biotech` — FDA 이벤트 갭, 임상 촉매, 유상증자·ATM, 낮은 float, 바이너리 이벤트, 숏스퀴즈 |
| Semiconductor | `sector_chart_semiconductor` — SOX 상대강도, 사이클, 어닝 갭, CapEx 사이클 |
| Bitcoin Equity | `sector_chart_bitcoin_equity` — BTC 상관·베타, 야간 크립토 변동, 채굴 경제성 |
| Small Cap | `sector_chart_smallcap` — Float, 프리마켓, RVOL, Gap%, HOD/LOD, 거래정지 |

---

## 5. 에이전트에게 주는 것 (§38)

차트 **이미지만** 주지 않습니다. 숫자를 함께 줍니다.

```python
{
  "recent_candles": [...],        # OHLCV 원시값
  "structure": {...},             # 위의 market_structure
  "indicators": {"rsi14":…, "atr14":…, "adx14":…},
  "relative": {"vs_sector":…, "vs_spx":…},
  "is_mock": true
}
```

LLM 은 이미지에서 숫자를 읽어낼 때 자주 틀립니다.
그래서 **계산은 코드가 하고, 해석만 LLM 이 합니다.**

Phase 16 에서 `mplfinance` 로 PNG 렌더를 추가해 이미지도 함께 제공합니다.

---

## 6. Technical Debate Team

| 에이전트 | 역할 |
|---|---|
| `technical_bull` | 상승 가능성을 증명 (role_prior +0.2) |
| `technical_bear` | 하락·실패 가능성을 증명 (role_prior −0.2) |
| `technical_judge` | **말투가 아니라 표본 수와 과거 유효성으로 판정** |

Judge 는 "설득력 있게 말한 쪽"이 아니라
"주장한 패턴의 과거 표본 수와 승률이 뒷받침되는 쪽"을 고릅니다.

---

## 7. Phase 16 에서 교체·확장

| 지금 | Phase 16 |
|---|---|
| 순수 파이썬 지표 | `pandas-ta-classic` (MIT) 기본 + `TA-Lib` (BSD) 선택적 가속 |
| — | `mplfinance` PNG 렌더 |
| 합성 캔들 | 실제 OHLCV |

**현재 구현은 사라지지 않습니다.** Phase 16 이후에도
"외부 라이브러리 값이 맞는지 대조하는 기준값"으로 남습니다.
