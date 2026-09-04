# AGENTS — 에이전트 조직도

> 이 문서는 `config/agents/*.yaml` 에서 자동 생성됩니다.
> 손으로 고치지 마세요. 설정을 고치면 문서도 따라옵니다.

- 총 정의: **177명**
- 지금 일하는 중(ACTIVE): **16명**
- 정의만 되어 있음(REGISTERED): **161명**

## 왜 전부 실행하지 않는가

177명을 항상 깨워두면 LLM 호출 비용이 폭발합니다.
Router 가 작업에 필요한 사람만 깨우고, 한 작업에서 **최대 8명**을 넘길 수 없습니다.
이 상한은 `packages/agent_registry/registry.py` 의 `Router.max_agents` 이고,
`wake_count_guard()` 가 초과 시 예외를 던집니다. 테스트로 검증합니다.

## 역할 (Role)

| Role | 인원 | 설명 |
|---|---|---|
| CIO | 1 | 최종 판단. 포트폴리오 관점에서 종합 |
| CHIEF_LEARNING_OFFICER | 1 | 학습 커리큘럼 설계와 감독 |
| SECTOR_LEAD | 49 | 섹터 총괄. 산업 구조와 경쟁 환경 |
| BULL_RESEARCHER | 49 | 상승 논거를 독립적으로 구축 |
| BEAR_RESEARCHER | 49 | 하락 논거를 독립적으로 구축 |
| TECHNICAL_MASTER | 1 | 멀티 타임프레임 차트 종합 |
| TECHNICAL_BULL | 1 | 기술적 상승 시나리오 입증 |
| TECHNICAL_BEAR | 1 | 기술적 하락/실패 시나리오 입증 |
| TECHNICAL_JUDGE | 1 | 표본 수와 과거 유효성으로 판정 |
| FUNDAMENTAL_MASTER | 1 | 재무제표와 단위경제성 |
| VALUATION_MASTER | 1 | 밸류에이션 |
| QUANT_MASTER | 1 | 팩터 연구와 백테스트 설계 |
| MACRO_EXPERT | 1 | 금리·물가·유동성 |
| RISK_EXPERT | 1 | 리스크 관리 |
| DATA_QUALITY | 1 | 데이터 검증과 시점 무결성 |
| SOURCE_VERIFICATION | 1 | 출처 검증, 중복·신디케이션 탐지 |
| EVIDENCE_JUDGE | 1 | 근거 없는 숫자 차단 |
| RED_TEAM | 1 | 가정 공격, 반대 근거 강제 탐색 |
| INVESTMENT_COMMITTEE | 1 | 에이전트 신뢰도를 가중해 합의 도출 |
| SPECIALIST | 14 | 세부 전문 영역 |

## 지금 일하고 있는 에이전트 (ACTIVE)

| ID | 이름 | 역할 | 부서 | 기본 자리 |
|---|---|---|---|---|
| `biotech_bear` | Biotechnology Bear Researcher | BEAR_RESEARCHER | Biotech Department | Biotech Department |
| `biotech_bull` | Biotechnology Bull Researcher | BULL_RESEARCHER | Biotech Department | Biotech Department |
| `biotech_lead` | Biotechnology Lead | SECTOR_LEAD | Biotech Department | Biotech Department |
| `technical_master` | Technical Master | TECHNICAL_MASTER | Chart Lab | Chart Lab |
| `data_quality` | Data Quality Agent | DATA_QUALITY | Data Quality | Data Center |
| `evidence_judge` | Evidence Judge | EVIDENCE_JUDGE | Data Quality | Risk Room |
| `source_verification` | Source Verification Expert | SOURCE_VERIFICATION | Data Quality | Data Center |
| `energy_bear` | Energy Bear Researcher | BEAR_RESEARCHER | Energy Department | Energy Department |
| `energy_bull` | Energy Bull Researcher | BULL_RESEARCHER | Energy Department | Energy Department |
| `energy_lead` | Energy Lead | SECTOR_LEAD | Energy Department | Energy Department |
| `cio` | Chief Investment Officer | CIO | Executive | CIO Office |
| `clo` | Chief Learning Officer | CHIEF_LEARNING_OFFICER | Executive | Research Library |
| `investment_committee` | Investment Committee | INVESTMENT_COMMITTEE | Executive | Investment Committee Room |
| `semiconductor_bear` | Semiconductor Bear Researcher | BEAR_RESEARCHER | Semiconductor Department | Semiconductor Department |
| `semiconductor_bull` | Semiconductor Bull Researcher | BULL_RESEARCHER | Semiconductor Department | Semiconductor Department |
| `semiconductor_lead` | Semiconductor Lead | SECTOR_LEAD | Semiconductor Department | Semiconductor Department |

## 부서별 전체 명단

### AI / Software Department  (24명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `ai_software_bear` | AI Software Bear Researcher | BEAR_RESEARCHER | ai_software | REGISTERED |
| `ai_software_bull` | AI Software Bull Researcher | BULL_RESEARCHER | ai_software | REGISTERED |
| `ai_software_lead` | AI Software Lead | SECTOR_LEAD | ai_software | REGISTERED |
| `cloud_saas_bear` | Cloud / SaaS Bear Researcher | BEAR_RESEARCHER | cloud_saas | REGISTERED |
| `cloud_saas_bull` | Cloud / SaaS Bull Researcher | BULL_RESEARCHER | cloud_saas | REGISTERED |
| `cloud_saas_lead` | Cloud / SaaS Lead | SECTOR_LEAD | cloud_saas | REGISTERED |
| `cybersecurity_bear` | Cybersecurity Bear Researcher | BEAR_RESEARCHER | cybersecurity | REGISTERED |
| `cybersecurity_bull` | Cybersecurity Bull Researcher | BULL_RESEARCHER | cybersecurity | REGISTERED |
| `cybersecurity_lead` | Cybersecurity Lead | SECTOR_LEAD | cybersecurity | REGISTERED |
| `data_center_bear` | Data Center Bear Researcher | BEAR_RESEARCHER | data_center | REGISTERED |
| `data_center_bull` | Data Center Bull Researcher | BULL_RESEARCHER | data_center | REGISTERED |
| `data_center_lead` | Data Center Lead | SECTOR_LEAD | data_center | REGISTERED |
| `networking_optical_bear` | Networking / Optical Bear Researcher | BEAR_RESEARCHER | networking_optical | REGISTERED |
| `networking_optical_bull` | Networking / Optical Bull Researcher | BULL_RESEARCHER | networking_optical | REGISTERED |
| `networking_optical_lead` | Networking / Optical Lead | SECTOR_LEAD | networking_optical | REGISTERED |
| `quantum_bear` | Quantum Computing Bear Researcher | BEAR_RESEARCHER | quantum | REGISTERED |
| `quantum_bull` | Quantum Computing Bull Researcher | BULL_RESEARCHER | quantum | REGISTERED |
| `quantum_lead` | Quantum Computing Lead | SECTOR_LEAD | quantum | REGISTERED |
| `robotics_bear` | Robotics / Humanoid Bear Researcher | BEAR_RESEARCHER | robotics | REGISTERED |
| `robotics_bull` | Robotics / Humanoid Bull Researcher | BULL_RESEARCHER | robotics | REGISTERED |
| `robotics_lead` | Robotics / Humanoid Lead | SECTOR_LEAD | robotics | REGISTERED |
| `server_infra_bear` | Server / Infrastructure Bear Researcher | BEAR_RESEARCHER | server_infra | REGISTERED |
| `server_infra_bull` | Server / Infrastructure Bull Researcher | BULL_RESEARCHER | server_infra | REGISTERED |
| `server_infra_lead` | Server / Infrastructure Lead | SECTOR_LEAD | server_infra | REGISTERED |

### Auto / Battery Department  (12명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `autonomous_bear` | Autonomous Driving Bear Researcher | BEAR_RESEARCHER | autonomous | REGISTERED |
| `autonomous_bull` | Autonomous Driving Bull Researcher | BULL_RESEARCHER | autonomous | REGISTERED |
| `autonomous_lead` | Autonomous Driving Lead | SECTOR_LEAD | autonomous | REGISTERED |
| `battery_bear` | Battery Bear Researcher | BEAR_RESEARCHER | battery | REGISTERED |
| `battery_bull` | Battery Bull Researcher | BULL_RESEARCHER | battery | REGISTERED |
| `battery_lead` | Battery Lead | SECTOR_LEAD | battery | REGISTERED |
| `ev_auto_bear` | EV / Automotive Bear Researcher | BEAR_RESEARCHER | ev_auto | REGISTERED |
| `ev_auto_bull` | EV / Automotive Bull Researcher | BULL_RESEARCHER | ev_auto | REGISTERED |
| `ev_auto_lead` | EV / Automotive Lead | SECTOR_LEAD | ev_auto | REGISTERED |
| `lithium_minerals_bear` | Lithium / Critical Minerals Bear Researcher | BEAR_RESEARCHER | lithium_minerals | REGISTERED |
| `lithium_minerals_bull` | Lithium / Critical Minerals Bull Researcher | BULL_RESEARCHER | lithium_minerals | REGISTERED |
| `lithium_minerals_lead` | Lithium / Critical Minerals Lead | SECTOR_LEAD | lithium_minerals | REGISTERED |

### Biotech Department  (6명 / ACTIVE 3명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `biotech_bear` | Biotechnology Bear Researcher | BEAR_RESEARCHER | biotech | **ACTIVE** |
| `biotech_bull` | Biotechnology Bull Researcher | BULL_RESEARCHER | biotech | **ACTIVE** |
| `biotech_lead` | Biotechnology Lead | SECTOR_LEAD | biotech | **ACTIVE** |
| `pharma_bear` | Pharmaceuticals Bear Researcher | BEAR_RESEARCHER | pharma | REGISTERED |
| `pharma_bull` | Pharmaceuticals Bull Researcher | BULL_RESEARCHER | pharma | REGISTERED |
| `pharma_lead` | Pharmaceuticals Lead | SECTOR_LEAD | pharma | REGISTERED |

### Chart Lab  (18명 / ACTIVE 1명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `catalyst_expert` | Catalyst Expert | SPECIALIST | – | REGISTERED |
| `insider_transaction_expert` | Insider Transaction Expert | SPECIALIST | – | REGISTERED |
| `institutional_flow_expert` | Institutional Flow Expert | SPECIALIST | – | REGISTERED |
| `market_structure_expert` | Market Structure Expert | SPECIALIST | – | REGISTERED |
| `momentum_expert` | Momentum Expert | SPECIALIST | – | REGISTERED |
| `news_intelligence_expert` | News Intelligence Expert | SPECIALIST | – | REGISTERED |
| `options_expert` | Options Expert | SPECIALIST | – | REGISTERED |
| `pattern_expert` | Pattern Expert | SPECIALIST | – | REGISTERED |
| `price_action_expert` | Price Action Expert | SPECIALIST | – | REGISTERED |
| `quant_master` | Quant Master | QUANT_MASTER | – | REGISTERED |
| `relative_strength_expert` | Relative Strength Expert | SPECIALIST | – | REGISTERED |
| `short_interest_expert` | Short Interest Expert | SPECIALIST | – | REGISTERED |
| `technical_bear` | Technical Bear | TECHNICAL_BEAR | – | REGISTERED |
| `technical_bull` | Technical Bull | TECHNICAL_BULL | – | REGISTERED |
| `technical_judge` | Technical Judge | TECHNICAL_JUDGE | – | REGISTERED |
| `technical_master` | Technical Master | TECHNICAL_MASTER | – | **ACTIVE** |
| `volatility_expert` | Volatility Expert | SPECIALIST | – | REGISTERED |
| `volume_expert` | Volume Expert | SPECIALIST | – | REGISTERED |

### Consumer / Industrial Department  (21명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `consumer_bear` | Consumer Bear Researcher | BEAR_RESEARCHER | consumer | REGISTERED |
| `consumer_bull` | Consumer Bull Researcher | BULL_RESEARCHER | consumer | REGISTERED |
| `consumer_lead` | Consumer Lead | SECTOR_LEAD | consumer | REGISTERED |
| `industrial_bear` | Industrial Bear Researcher | BEAR_RESEARCHER | industrial | REGISTERED |
| `industrial_bull` | Industrial Bull Researcher | BULL_RESEARCHER | industrial | REGISTERED |
| `industrial_lead` | Industrial Lead | SECTOR_LEAD | industrial | REGISTERED |
| `infrastructure_bear` | Infrastructure Bear Researcher | BEAR_RESEARCHER | infrastructure | REGISTERED |
| `infrastructure_bull` | Infrastructure Bull Researcher | BULL_RESEARCHER | infrastructure | REGISTERED |
| `infrastructure_lead` | Infrastructure Lead | SECTOR_LEAD | infrastructure | REGISTERED |
| `materials_bear` | Materials Bear Researcher | BEAR_RESEARCHER | materials | REGISTERED |
| `materials_bull` | Materials Bull Researcher | BULL_RESEARCHER | materials | REGISTERED |
| `materials_lead` | Materials Lead | SECTOR_LEAD | materials | REGISTERED |
| `reit_bear` | REIT Bear Researcher | BEAR_RESEARCHER | reit | REGISTERED |
| `reit_bull` | REIT Bull Researcher | BULL_RESEARCHER | reit | REGISTERED |
| `reit_lead` | REIT Lead | SECTOR_LEAD | reit | REGISTERED |
| `retail_bear` | Retail Bear Researcher | BEAR_RESEARCHER | retail | REGISTERED |
| `retail_bull` | Retail Bull Researcher | BULL_RESEARCHER | retail | REGISTERED |
| `retail_lead` | Retail Lead | SECTOR_LEAD | retail | REGISTERED |
| `small_cap_bear` | Small Cap / Special Situations Bear Researcher | BEAR_RESEARCHER | small_cap | REGISTERED |
| `small_cap_bull` | Small Cap / Special Situations Bull Researcher | BULL_RESEARCHER | small_cap | REGISTERED |
| `small_cap_lead` | Small Cap / Special Situations Lead | SECTOR_LEAD | small_cap | REGISTERED |

### Data Quality  (4명 / ACTIVE 3명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `data_quality` | Data Quality Agent | DATA_QUALITY | – | **ACTIVE** |
| `evidence_judge` | Evidence Judge | EVIDENCE_JUDGE | – | **ACTIVE** |
| `red_team` | Red Team | RED_TEAM | – | REGISTERED |
| `source_verification` | Source Verification Expert | SOURCE_VERIFICATION | – | **ACTIVE** |

### Defense / Space Department  (12명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `defense_bear` | Defense Bear Researcher | BEAR_RESEARCHER | defense | REGISTERED |
| `defense_bull` | Defense Bull Researcher | BULL_RESEARCHER | defense | REGISTERED |
| `defense_lead` | Defense Lead | SECTOR_LEAD | defense | REGISTERED |
| `drone_bear` | Drone Bear Researcher | BEAR_RESEARCHER | drone | REGISTERED |
| `drone_bull` | Drone Bull Researcher | BULL_RESEARCHER | drone | REGISTERED |
| `drone_lead` | Drone Lead | SECTOR_LEAD | drone | REGISTERED |
| `satellite_bear` | Satellite Bear Researcher | BEAR_RESEARCHER | satellite | REGISTERED |
| `satellite_bull` | Satellite Bull Researcher | BULL_RESEARCHER | satellite | REGISTERED |
| `satellite_lead` | Satellite Lead | SECTOR_LEAD | satellite | REGISTERED |
| `space_bear` | Space Bear Researcher | BEAR_RESEARCHER | space | REGISTERED |
| `space_bull` | Space Bull Researcher | BULL_RESEARCHER | space | REGISTERED |
| `space_lead` | Space Lead | SECTOR_LEAD | space | REGISTERED |

### Energy Department  (36명 / ACTIVE 3명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `energy_bear` | Energy Bear Researcher | BEAR_RESEARCHER | energy | **ACTIVE** |
| `energy_bull` | Energy Bull Researcher | BULL_RESEARCHER | energy | **ACTIVE** |
| `energy_lead` | Energy Lead | SECTOR_LEAD | energy | **ACTIVE** |
| `energy_services_bear` | Energy Services Bear Researcher | BEAR_RESEARCHER | energy_services | REGISTERED |
| `energy_services_bull` | Energy Services Bull Researcher | BULL_RESEARCHER | energy_services | REGISTERED |
| `energy_services_lead` | Energy Services Lead | SECTOR_LEAD | energy_services | REGISTERED |
| `ess_bear` | ESS Bear Researcher | BEAR_RESEARCHER | ess | REGISTERED |
| `ess_bull` | ESS Bull Researcher | BULL_RESEARCHER | ess | REGISTERED |
| `ess_lead` | ESS Lead | SECTOR_LEAD | ess | REGISTERED |
| `hydrogen_bear` | Hydrogen Bear Researcher | BEAR_RESEARCHER | hydrogen | REGISTERED |
| `hydrogen_bull` | Hydrogen Bull Researcher | BULL_RESEARCHER | hydrogen | REGISTERED |
| `hydrogen_lead` | Hydrogen Lead | SECTOR_LEAD | hydrogen | REGISTERED |
| `lng_bear` | LNG Bear Researcher | BEAR_RESEARCHER | lng | REGISTERED |
| `lng_bull` | LNG Bull Researcher | BULL_RESEARCHER | lng | REGISTERED |
| `lng_lead` | LNG Lead | SECTOR_LEAD | lng | REGISTERED |
| `nuclear_bear` | Nuclear Bear Researcher | BEAR_RESEARCHER | nuclear | REGISTERED |
| `nuclear_bull` | Nuclear Bull Researcher | BULL_RESEARCHER | nuclear | REGISTERED |
| `nuclear_lead` | Nuclear Lead | SECTOR_LEAD | nuclear | REGISTERED |
| `oil_bear` | Oil Bear Researcher | BEAR_RESEARCHER | oil | REGISTERED |
| `oil_bull` | Oil Bull Researcher | BULL_RESEARCHER | oil | REGISTERED |
| `oil_lead` | Oil Lead | SECTOR_LEAD | oil | REGISTERED |
| `power_grid_bear` | Power Grid Bear Researcher | BEAR_RESEARCHER | power_grid | REGISTERED |
| `power_grid_bull` | Power Grid Bull Researcher | BULL_RESEARCHER | power_grid | REGISTERED |
| `power_grid_lead` | Power Grid Lead | SECTOR_LEAD | power_grid | REGISTERED |
| `smr_bear` | SMR Bear Researcher | BEAR_RESEARCHER | smr | REGISTERED |
| `smr_bull` | SMR Bull Researcher | BULL_RESEARCHER | smr | REGISTERED |
| `smr_lead` | SMR Lead | SECTOR_LEAD | smr | REGISTERED |
| `solar_bear` | Solar Bear Researcher | BEAR_RESEARCHER | solar | REGISTERED |
| `solar_bull` | Solar Bull Researcher | BULL_RESEARCHER | solar | REGISTERED |
| `solar_lead` | Solar Lead | SECTOR_LEAD | solar | REGISTERED |
| `uranium_bear` | Uranium Bear Researcher | BEAR_RESEARCHER | uranium | REGISTERED |
| `uranium_bull` | Uranium Bull Researcher | BULL_RESEARCHER | uranium | REGISTERED |
| `uranium_lead` | Uranium Lead | SECTOR_LEAD | uranium | REGISTERED |
| `utilities_bear` | Utilities Bear Researcher | BEAR_RESEARCHER | utilities | REGISTERED |
| `utilities_bull` | Utilities Bull Researcher | BULL_RESEARCHER | utilities | REGISTERED |
| `utilities_lead` | Utilities Lead | SECTOR_LEAD | utilities | REGISTERED |

### Executive  (3명 / ACTIVE 3명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `cio` | Chief Investment Officer | CIO | – | **ACTIVE** |
| `clo` | Chief Learning Officer | CHIEF_LEARNING_OFFICER | – | **ACTIVE** |
| `investment_committee` | Investment Committee | INVESTMENT_COMMITTEE | – | **ACTIVE** |

### Finance / Crypto Department  (15명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `banking_bear` | Banking Bear Researcher | BEAR_RESEARCHER | banking | REGISTERED |
| `banking_bull` | Banking Bull Researcher | BULL_RESEARCHER | banking | REGISTERED |
| `banking_lead` | Banking Lead | SECTOR_LEAD | banking | REGISTERED |
| `bitcoin_equity_bear` | Bitcoin Related Equity Bear Researcher | BEAR_RESEARCHER | bitcoin_equity | REGISTERED |
| `bitcoin_equity_bull` | Bitcoin Related Equity Bull Researcher | BULL_RESEARCHER | bitcoin_equity | REGISTERED |
| `bitcoin_equity_lead` | Bitcoin Related Equity Lead | SECTOR_LEAD | bitcoin_equity | REGISTERED |
| `crypto_infra_bear` | Crypto Infrastructure Bear Researcher | BEAR_RESEARCHER | crypto_infra | REGISTERED |
| `crypto_infra_bull` | Crypto Infrastructure Bull Researcher | BULL_RESEARCHER | crypto_infra | REGISTERED |
| `crypto_infra_lead` | Crypto Infrastructure Lead | SECTOR_LEAD | crypto_infra | REGISTERED |
| `fintech_bear` | Fintech Bear Researcher | BEAR_RESEARCHER | fintech | REGISTERED |
| `fintech_bull` | Fintech Bull Researcher | BULL_RESEARCHER | fintech | REGISTERED |
| `fintech_lead` | Fintech Lead | SECTOR_LEAD | fintech | REGISTERED |
| `insurance_bear` | Insurance Bear Researcher | BEAR_RESEARCHER | insurance | REGISTERED |
| `insurance_bull` | Insurance Bull Researcher | BULL_RESEARCHER | insurance | REGISTERED |
| `insurance_lead` | Insurance Lead | SECTOR_LEAD | insurance | REGISTERED |

### Healthcare Department  (6명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `healthcare_bear` | Healthcare Bear Researcher | BEAR_RESEARCHER | healthcare | REGISTERED |
| `healthcare_bull` | Healthcare Bull Researcher | BULL_RESEARCHER | healthcare | REGISTERED |
| `healthcare_lead` | Healthcare Lead | SECTOR_LEAD | healthcare | REGISTERED |
| `medical_devices_bear` | Medical Devices Bear Researcher | BEAR_RESEARCHER | medical_devices | REGISTERED |
| `medical_devices_bull` | Medical Devices Bull Researcher | BULL_RESEARCHER | medical_devices | REGISTERED |
| `medical_devices_lead` | Medical Devices Lead | SECTOR_LEAD | medical_devices | REGISTERED |

### Research Library  (4명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `accounting_forensics` | Accounting Forensics Expert | SPECIALIST | – | REGISTERED |
| `fundamental_master` | Fundamental Master | FUNDAMENTAL_MASTER | – | REGISTERED |
| `macro_expert` | Macro Expert | MACRO_EXPERT | – | REGISTERED |
| `valuation_master` | Valuation Master | VALUATION_MASTER | – | REGISTERED |

### Risk Room  (1명 / ACTIVE 0명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `risk_expert` | Risk Expert | RISK_EXPERT | – | REGISTERED |

### Semiconductor Department  (15명 / ACTIVE 3명)

| ID | 이름 | 역할 | 섹터 | 상태 |
|---|---|---|---|---|
| `ai_gpu_bear` | AI / GPU Bear Researcher | BEAR_RESEARCHER | ai_gpu | REGISTERED |
| `ai_gpu_bull` | AI / GPU Bull Researcher | BULL_RESEARCHER | ai_gpu | REGISTERED |
| `ai_gpu_lead` | AI / GPU Lead | SECTOR_LEAD | ai_gpu | REGISTERED |
| `hbm_memory_bear` | HBM / Memory Bear Researcher | BEAR_RESEARCHER | hbm_memory | REGISTERED |
| `hbm_memory_bull` | HBM / Memory Bull Researcher | BULL_RESEARCHER | hbm_memory | REGISTERED |
| `hbm_memory_lead` | HBM / Memory Lead | SECTOR_LEAD | hbm_memory | REGISTERED |
| `semi_equipment_bear` | Semiconductor Equipment Bear Researcher | BEAR_RESEARCHER | semi_equipment | REGISTERED |
| `semi_equipment_bull` | Semiconductor Equipment Bull Researcher | BULL_RESEARCHER | semi_equipment | REGISTERED |
| `semi_equipment_lead` | Semiconductor Equipment Lead | SECTOR_LEAD | semi_equipment | REGISTERED |
| `semi_materials_bear` | Semiconductor Materials Bear Researcher | BEAR_RESEARCHER | semi_materials | REGISTERED |
| `semi_materials_bull` | Semiconductor Materials Bull Researcher | BULL_RESEARCHER | semi_materials | REGISTERED |
| `semi_materials_lead` | Semiconductor Materials Lead | SECTOR_LEAD | semi_materials | REGISTERED |
| `semiconductor_bear` | Semiconductor Bear Researcher | BEAR_RESEARCHER | semiconductor | **ACTIVE** |
| `semiconductor_bull` | Semiconductor Bull Researcher | BULL_RESEARCHER | semiconductor | **ACTIVE** |
| `semiconductor_lead` | Semiconductor Lead | SECTOR_LEAD | semiconductor | **ACTIVE** |

## 에이전트 프로필에 들어가는 것

```yaml
id: semiconductor_bull
name: Semiconductor Bull Researcher
department: Semiconductor Department
role: BULL_RESEARCHER
sector: semiconductor
status: ACTIVE            # ACTIVE | REGISTERED | SLEEPING
specialties: [...]
skills:
  - common_chart_skill        # 모든 섹터 에이전트 기본 장착
  - sector_chart_semiconductor
model_policy:
  default: tier_strong        # ★ 실제 모델명이 아니라 '등급'
  cheap_tasks: tier_cheap
research_depth: 10
learning_target_minutes: 240
home_location: Semiconductor Department
role_prior: 0.15            # Bull 은 +, Bear 는 -
```

### 왜 모델명을 등급으로 쓰는가

프로필에 실제 모델 ID 를 박으면 177개 파일을 전부 고쳐야 모델을 바꿀 수 있습니다.
등급(`tier_strong` 등)만 쓰고 실제 매핑은 `config/models.yaml` **한 곳**에서만 합니다.
테스트가 프로필에 실제 모델명이 들어가는 것을 막습니다.

### role_prior 는 편향인가

아닙니다. Bull 과 Bear 는 각자 자기 쪽 논거를 **끝까지 밀어붙이는 역할**입니다.
출발점만 살짝 기울어 있고, 예측이 틀리면 학습이 가중치를 교정합니다.
그래서 시간이 지나면 Bull 이 하락을 말하는 경우도 생깁니다.
