# BACKTEST

구현: `packages/backtest_engine/`
테스트: `tests/test_backtest_and_patterns.py`

---

## 1. 이 엔진이 지키는 한 가지

> **신호는 T 종가에 나오고, 체결은 T+1 시가에 이뤄집니다.**

같은 봉의 종가에 체결하면 그것만으로 이미 미래를 쓴 것입니다.
이 한 줄 때문에 수많은 백테스트가 거짓말을 합니다.

---

## 2. 구조

```python
for t in range(warmup, n - 1):
    past = series[: t + 1]        # ★ 미래 봉은 인자로 존재하지 않음
    signal = strategy(past, current_weight)

    next_bar = series[t + 1]
    fill_price = next_bar.open * (1 ± slippage)   # T+1 시가 체결
    equity -= turnover * commission
    equity *= (1 + weight * period_return)
```

전략 함수는 `past` 만 받습니다. **미래를 볼 통로가 없습니다.**

---

## 3. 누수 감시 리포트

모든 백테스트 결과에 포함됩니다.

```json
"leak_guard": {
  "max_bar_index_shown_to_strategy": 598,
  "last_bar_index": 599,
  "future_bars_never_shown": 1,
  "execution_rule": "신호는 T 종가, 체결은 T+1 시가",
  "note": "전략 함수에는 series[:t+1] 만 전달됩니다."
}
```

UI 의 Backtest 화면에 그대로 표시됩니다.

---

## 4. 비용 모델

| 항목 | 기본값 | 설명 |
|---|---|---|
| 수수료 | 5 bp (0.05%) | 편도. 회전율에 비례 |
| 슬리피지 | 5 bp | 편도. 매수 시 불리하게, 매도 시 불리하게 |

`test_costs_reduce_returns` 가 비용이 실제로 수익을 깎는지 검증합니다.

---

## 5. 성과 지표

```
total_return, CAGR, volatility, Sharpe, Sortino,
max_drawdown, Calmar, win_rate, profit_factor,
beta, alpha_annual, benchmark_return, excess_return,
trades, trade_win_rate, avg_trade
```

### 검증된 것

- `max_drawdown([100,120,90,130])` = −25% ✅
- 1년에 2배 되는 곡선의 CAGR = 100% ✅
- 자기 자신 대비 베타 = 1.0 ✅
- 현금 보유 전략의 자산곡선은 완전히 평평 ✅
- 매수 후 보유는 가격 수익률을 추종 ✅

Phase 19 에서 QuantStats(Apache-2.0)로 교차검증할 수 있지만,
이 구현은 **기준값**으로 남습니다.

---

## 6. 내장 전략 (엔진 검증용)

| 전략 | 설명 |
|---|---|
| `sma_crossover` | SMA20 > SMA50 이면 매수 |
| `buy_and_hold` | 매수 후 보유 |
| `flat` | 현금 보유 (대조군) |

**이 전략들이 돈을 번다는 뜻이 아닙니다.** 엔진이 제대로 도는지 확인하는 용도입니다.

---

## 7. 실행

UI: Backtest 메뉴 → 티커/전략/수수료/슬리피지 입력 → 실행

API:
```
POST /api/backtest
{"ticker":"NVDA","strategy":"sma_crossover","commission_bps":5,"slippage_bps":5}
```

실행하면 Quant Master 와 Technical Master 가 픽셀 사무실에서
**Backtest Lab 으로 실제로 이동합니다.** 연출이 아니라 상태 변경입니다.

---

## 8. 아직 없는 것 (Phase 19)

- 상장폐지 종목 처리 (생존 편향)
- 배당·분할 조정
- 다종목 포트폴리오 리밸런싱
- 공매도 / 레버리지 (현재 비중 0~1 만 지원)
- 시장 국면별 분리 평가
- 거래일 캘린더 (`exchange_calendars`) 연동 — 지금은 봉 인덱스 기준

**가장 중요한 미비점: 실제 시장 데이터가 아직 없습니다.**
현재 결과는 합성 데이터 기반이며 실전 성과를 전혀 시사하지 않습니다.
