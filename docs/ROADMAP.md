# ROADMAP

최종 갱신 2026-09-03 · 상세 현황은 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md)

---

## 완료

| Phase | 내용 | 검증 |
|---|---|---|
| 0 | 환경 Audit 스크립트 | 구문검사 통과 (사용자 PC 실행 대기) |
| 1 | GitHub Deep Research (22개 저장소) | `docs/GITHUB_RESEARCH.md` |
| 2 | License Audit — RED 3건 배제 | `docs/LICENSE_AUDIT.md` |
| 3 | Architecture | `docs/ARCHITECTURE.md` |
| 4 | Repository Scaffold | 130개 파일 커밋 |
| 5 | Backend (FastAPI + standalone) | 엔드포인트 15개 실측 |
| 6 | Frontend Shell | 화면 10개, 콘솔 오류 0 |
| 7 | **Pixel Office** | 스크린샷 렌더링 확인 |
| 8 | Agent Registry (177명/49섹터) | 레지스트리 테스트 |
| 9 | **Realtime WebSocket** | 원시 소켓 클라이언트 검증 |
| 10 | Research Workflow | 인수 시나리오 5~8 |
| 13 | **Research Firewall** | 25개 테스트 |
| 14 | Sector Teams | 반도체·바이오·에너지 ACTIVE |
| 15 | **Bull/Bear Debate** | 채널 격리 검증 |
| 16 | Chart Engine | 지표 24개 테스트 |
| 17 | **Learning Engine** | 실제 학습 동작 확인 |
| 18 | Prediction Journal | Trust Score 산출 |
| 19 | **Backtest Engine** | 누수 감시 통과 |
| 20 | **Pattern Miner** | 3구간 검증 + 과적합 방지 |
| 22 | Quality (테스트 164 + 인수 66) | 전부 통과 |
| 23 | Final Acceptance (15 시나리오) | **66/66 통과** |

---

## 다음

### Phase 21 — 실제 시장 데이터 ★ 최우선
- `packages/data_connectors` Provider 구현 (yfinance)
- `exchange_calendars` 통합 — 거래일 계산
- `pit_store` 를 실제 데이터로
- Markets 화면 구현 (지금은 일부러 비워둠)

### Phase 12 — SEC EDGAR
- edgartools, User-Agent 규칙, 초당 10요청 제한
- `filing_date` vs `period_of_report` 분리 저장
- 정정 공시 버전 관리

### Phase 5b — PostgreSQL 영속화
- Alembic 마이그레이션, pgvector
- 현재 메모리 상태를 DB로
- Redis 라이선스 재확인 (Valkey 로 이미 대비)

### Phase 10b — LLM 연결 ⚠️ API 키 필요
- LiteLLM + `llm_gateway` 인터페이스
- 심층 추론·토론·실패분석에만 사용
- 비용 대시보드 활성화

### Phase 20b — Pattern Miner 강화
- Walk-forward 검증
- **다중검정 보정** (현재 가장 큰 통계적 약점)
- 시장 국면별 분리

### Phase 21b — 다중 시장
- DART(한국) · TWSE/TPEX(대만) · Spotlight(스웨덴)
- antking님의 실제 관심 시장

---

## 하지 않는 것

- **실제 증권계좌 연동 / 주문 실행** — 범위 밖. 착수하려면 별도 승인 필요
- 멀티 유저 / 클라우드 배포
- 자체 금융 LLM 파인튜닝

---

## 사용자 결정 대기

| 항목 | 필요 시점 |
|---|---|
| `audit.ps1` 실행 결과 | 지금 |
| lightweight-charts 채택 여부 (TradingView 표기) | Phase 21 |
| **LLM API 키** (비용 발생) | Phase 10b |
| 유료 데이터 API (비용 발생) | Phase 21 |
