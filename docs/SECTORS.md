# SECTORS — 섹터 조직

> `config/agents/*.yaml` 에서 자동 생성됩니다.

총 **49개 섹터**. 각 섹터는 **Lead / Bull / Bear 3명**으로 구성됩니다.

## 핵심 규칙

**Bull 과 Bear 는 최초 분석 단계에서 서로의 결과를 볼 수 없습니다.**

이건 프롬프트로 부탁하는 게 아니라 데이터 구조로 막습니다.
LangGraph state 에서 `bull_channel` 과 `bear_channel` 을 분리하고,
DEBATE 노드 이전에는 상대 채널이 컨텍스트에 들어가지 않습니다.

```
BULL_RESEARCH  ──┐
                 ├─→ CONTRADICTION_SEARCH ─→ DEBATE ─→ EVIDENCE_GATE ─→ JUDGE
BEAR_RESEARCH  ──┘        (반대 검색어 자동 생성)
     ↑
  서로 못 봄
```

## 섹터 목록

| 섹터 키 | 부서 | Lead | Bull | Bear | 상태 |
|---|---|---|---|---|---|
| `ai_gpu` | Semiconductor Department | ✅ | ✅ | ✅ | REGISTERED |
| `ai_software` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `autonomous` | Auto / Battery Department | ✅ | ✅ | ✅ | REGISTERED |
| `banking` | Finance / Crypto Department | ✅ | ✅ | ✅ | REGISTERED |
| `battery` | Auto / Battery Department | ✅ | ✅ | ✅ | REGISTERED |
| `biotech` | Biotech Department | ✅ | ✅ | ✅ | **ACTIVE** |
| `bitcoin_equity` | Finance / Crypto Department | ✅ | ✅ | ✅ | REGISTERED |
| `cloud_saas` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `consumer` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `crypto_infra` | Finance / Crypto Department | ✅ | ✅ | ✅ | REGISTERED |
| `cybersecurity` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `data_center` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `defense` | Defense / Space Department | ✅ | ✅ | ✅ | REGISTERED |
| `drone` | Defense / Space Department | ✅ | ✅ | ✅ | REGISTERED |
| `energy` | Energy Department | ✅ | ✅ | ✅ | **ACTIVE** |
| `energy_services` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `ess` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `ev_auto` | Auto / Battery Department | ✅ | ✅ | ✅ | REGISTERED |
| `fintech` | Finance / Crypto Department | ✅ | ✅ | ✅ | REGISTERED |
| `hbm_memory` | Semiconductor Department | ✅ | ✅ | ✅ | REGISTERED |
| `healthcare` | Healthcare Department | ✅ | ✅ | ✅ | REGISTERED |
| `hydrogen` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `industrial` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `infrastructure` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `insurance` | Finance / Crypto Department | ✅ | ✅ | ✅ | REGISTERED |
| `lithium_minerals` | Auto / Battery Department | ✅ | ✅ | ✅ | REGISTERED |
| `lng` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `materials` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `medical_devices` | Healthcare Department | ✅ | ✅ | ✅ | REGISTERED |
| `networking_optical` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `nuclear` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `oil` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `pharma` | Biotech Department | ✅ | ✅ | ✅ | REGISTERED |
| `power_grid` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `quantum` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `reit` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `retail` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `robotics` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `satellite` | Defense / Space Department | ✅ | ✅ | ✅ | REGISTERED |
| `semi_equipment` | Semiconductor Department | ✅ | ✅ | ✅ | REGISTERED |
| `semi_materials` | Semiconductor Department | ✅ | ✅ | ✅ | REGISTERED |
| `semiconductor` | Semiconductor Department | ✅ | ✅ | ✅ | **ACTIVE** |
| `server_infra` | AI / Software Department | ✅ | ✅ | ✅ | REGISTERED |
| `small_cap` | Consumer / Industrial Department | ✅ | ✅ | ✅ | REGISTERED |
| `smr` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `solar` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `space` | Defense / Space Department | ✅ | ✅ | ✅ | REGISTERED |
| `uranium` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |
| `utilities` | Energy Department | ✅ | ✅ | ✅ | REGISTERED |

## 섹터별 특수 차트 스킬

산업마다 가격이 움직이는 방식이 다릅니다. 공통 차트 스킬 위에 얹습니다.

| 섹터 | 추가 스킬 | 이유 |
|---|---|---|
| Biotech / Pharma | FDA 이벤트 갭, 임상 촉매, 유상증자·ATM 리스크, 낮은 유통주식수, 바이너리 이벤트, 숏스퀴즈 | 임상 결과 하나로 하루에 ±60% 가 납니다. 일반 기술적 분석이 통하지 않습니다 |
| Semiconductor | SOX 상대강도, 사이클, 어닝 갭, CapEx 사이클, 산업 상대강도 | 개별 종목보다 사이클과 업종 흐름이 지배적입니다 |
| Bitcoin Equity | BTC 상관·베타, 야간 크립토 변동, 채굴 경제성, 비트코인 보유 프리미엄 | 주식이지만 코인 시세에 24시간 끌려다닙니다 |
| Small Cap | Float, 프리마켓 거래량, RVOL, Gap%, HOD/LOD, VWAP, 거래정지, 유상증자 리스크 | 유동성이 얇아 수급이 전부입니다 |

## 활성화 정책

MVP 에서는 **반도체 / 바이오 / 에너지** 3개 섹터만 ACTIVE 입니다.
나머지는 프로필만 존재하고 LLM 호출이 발생하지 않습니다.

섹터를 켜려면 해당 YAML 의 `status` 를 `REGISTERED` → `ACTIVE` 로 바꾸고 재시작하면 됩니다.

다만 한 번에 다 켜지 마세요. 활성 에이전트가 늘면 그만큼 비용과 부하가 늘어납니다.
