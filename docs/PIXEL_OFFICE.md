# PIXEL OFFICE

구현: `services/api/static/office.html` (단일 파일, 의존성 0)
배치: `config/office_layout.yaml`

---

## 1. 원칙: 프론트엔드는 상태를 지어내지 않는다

캐릭터가 움직이는 이유는 **전부 백엔드 이벤트**입니다.
이벤트가 없으면 캐릭터는 가만히 있습니다.

```
agent_runtime 에서 상태 변경
   ↓
EventBus.emit("agent.status_changed", is_mock=True, ...)
   ↓
WebSocket /ws/events
   ↓
Canvas 2D 렌더러가 목적지 갱신 → 캐릭터가 걸어감
```

모든 이벤트에 **`is_mock` 플래그가 강제**됩니다.
`test_every_event_carries_is_mock` 이 이걸 검증합니다.

---

## 2. 왜 PixiJS 가 아니라 Canvas 2D 인가

| | PixiJS 8 | Canvas 2D |
|---|---|---|
| 라이선스 | MIT | 브라우저 내장 |
| 번들 | 큼 | 0 |
| 동시 스프라이트 | 수천 개 | 수백 개까지 충분 |
| 학습·디버깅 비용 | 높음 | 낮음 |

MVP 동시 표시 캐릭터는 **16명**입니다. WebGL 엔진이 필요한 규모가 아닙니다.
게다가 ⭐9.2k 짜리 `pixel-agents` 프로젝트도 Canvas 2D 로 같은 UX 를 구현합니다.

렌더러는 교체 가능한 구조로 두었습니다. 캐릭터가 60명을 넘고 프레임이 떨어지면
PixiJS 구현체를 추가하면 됩니다. (docs/DECISIONS.md D-001)

---

## 3. 사무실 배치 (21개 공간)

```
Research Library  |  Chart Lab  |  Data Center  |  Risk Room
─────────────────────────────────────────────────────────────
Semiconductor  |  AI/Software  |  Biotech  |  Healthcare
                                          |  Energy
─────────────────────────────────────────────────────────────
Auto/Battery | Defense/Space | Finance/Crypto | Consumer/Industrial
─────────────────────────────────────────────────────────────
Backtest Lab  |  Learning Room
─────────────────────────────────────────────────────────────
Bull/Bear Debate Room | Investment Committee | CIO Office
```

배치는 **백엔드가 원본**입니다. 부서를 추가하려면 `config/office_layout.yaml` 만 고치면 됩니다.

---

## 4. 상태 → 장소 매핑

| 상태 | 이동 장소 | 언제 |
|---|---|---|
| `SEARCHING` / `RESEARCHING` / `READING` | Research Library | 자료 정독 |
| `VERIFYING` | Data Center | 출처 검증 |
| `CHARTING` | Chart Lab | 차트 학습 |
| `LEARNING` | Learning Room | 시험 |
| `DEBATING` | Bull/Bear Debate Room | 토론 |
| `BACKTESTING` | Backtest Lab | 백테스트 |
| `EVALUATING` | Risk Room | 예측 복기·근거 심사 |
| `COMMITTEE` | Investment Committee | 위원회 심의 |
| `CIO_REVIEW` | CIO Office | 최종 검토 |
| `IDLE` / `WAITING` / `BLOCKED` / `SLEEPING` / `ERROR` | 자기 자리 | |

전체 상태: `SLEEPING, IDLE, WALKING, SEARCHING, RESEARCHING, READING,
CHARTING, LEARNING, DEBATING, VERIFYING, BACKTESTING, EVALUATING,
COMMITTEE, CIO_REVIEW, WAITING, BLOCKED, DONE, ERROR`

---

## 5. 캐릭터 클릭 → Right Drawer

표시 항목:

```
이름 / 역할 / 부서 / 섹터
현재 상태 · 위치 · 업무 · 분석 종목 · 현재 판단(BULL/BEAR) · 확신도
리서치 깊이 · 모델 등급

오늘 학습: 유효학습/목표, 진행률, 학습효율, 제외된 시간(사유별 내역)
점수:     차트 스킬, 예측 정확도, 최근 정확도, 캘리브 오차, 표본 수,
          일일 차트시험, 출처 검증시험, 섹터 지식
자료:     읽은 출처, 거른 출처, 추가된 지식, 기각된 지식, 차트문제, 예측복기
최근 발견 / 최근 실수(오답 분류) / 최근 학습 기록
학습된 모델 가중치 (실제 숫자)
예측 성적 (Trust Score 포함)
```

**모델 가중치를 그대로 보여줍니다.** 장식이 아니라 실제로 갱신되는 값이기 때문입니다.

---

## 6. 캐릭터가 몰리지 않게 하는 장치

에이전트 시작 단계를 ID 해시로 어긋나게 배치합니다.

```python
st._step = sum(ord(c) for c in agent_id) % len(program)
```

이게 없으면 16명이 한 방에 몰려 있다가 다 같이 다른 방으로 우르르 옮겨갑니다.
사무실처럼 보이지도 않고, 계산 부하도 한 순간에 몰립니다.

이름표는 붐빌 때 자동으로 줄이 어긋나고 이름이 짧아집니다.

---

## 7. 화면 구성

상단 바: MOCK DATA 배지 · LLM 연결 상태 · 실시간 연결 상태 ·
활동/리서치/학습/막힘 에이전트 수 · 작업 큐 · 학습 일차 · 승인 지식 · LLM 비용

좌측 메뉴 10개: Office / Research / Agents / Learning / Markets /
Data / Backtest / Patterns / Audit / Settings

주소창 해시로 바로 이동 가능: `http://localhost:8010/#learning`

---

## 8. MOCK 배지는 끌 수 없습니다

`mock_mode` 가 true 인 동안 배지는 항상 떠 있습니다.
가짜 데이터를 실제처럼 보이게 만드는 것은 이 프로젝트에서 가장 하면 안 되는 일입니다.

Markets 화면은 **일부러 비워두었습니다.** 없는 데이터를 있는 것처럼 그리는 대신
"아직 구현되지 않았습니다 (Phase 21)" 라고 적어두었습니다.
