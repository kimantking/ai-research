# AGENT REACH 통합

- 검토일: **2026-09-03**
- 대상: https://github.com/Panniantong/agent-reach
- 결론: **🟡 조건부 채택 — 선택 설치, 자격증명 채널 기본 차단, 결과는 전부 방화벽 통과**

---

## 1. 무엇인가

AI 에이전트에게 인터넷 접근을 주는 CLI 도구입니다.
웹페이지 읽기(Jina Reader), RSS, YouTube 자막, GitHub, Reddit, Twitter,
빌리빌리, 샤오홍슈 등을 **하나의 CLI** 로 감싸줍니다.

우리에게 매력적인 이유: **Phase 21(실데이터 수집)에서 크롤러 10개를 직접 만들 필요가 없습니다.**

---

## 2. 검증한 것과 못 한 것 (정직하게)

| 항목 | 확인 방법 | 결과 |
|---|---|---|
| 설치 문서 | 원문 직접 fetch | ✅ 확인 |
| 저장소 개요·라이선스 | GitHub 저장소 페이지 | **MIT 로 표기됨** |
| LICENSE 파일 원문 | ❌ 접근 승인 안 됨 | **직접 확인 못 함** |
| Star 수 | 요약본 | **수치를 신뢰하지 않습니다** (검증 실패) |
| 실제 동작 | ❌ 이 환경에서 설치 불가 (403) | **미검증** |

> **중요**: 저는 이 도구를 **실행해본 적이 없습니다.**
> 이 문서는 문서와 저장소 페이지를 읽고 쓴 것입니다.
> 실제 동작은 antking님이 설치하신 뒤에야 확인됩니다.

---

## 3. 왜 이 세션에서 설치하지 않았나

두 가지입니다.

1. **물리적으로 불가능** — 이 클라우드 컨테이너는 GitHub 아카이브 다운로드와
   PyPI 를 정책상 차단합니다 (둘 다 403). 우회하면 안 되는 종류의 차단입니다.
2. **의미가 없음** — Agent Reach 는 에이전트에게 인터넷을 주는 도구인데,
   우리 시스템은 antking님 Windows PC 에서 돕니다. 여기 설치하면 세션 종료와 함께 사라집니다.

그래서 **어댑터 계층을 미리 만들어두었습니다.** 설치하시면 자동으로 감지합니다.

---

## 4. 위험 (숨기지 않습니다)

### 4-1. 쿠키 기반 인증 ⚠️ 가장 큰 위험

Twitter / Instagram / LinkedIn / 샤오홍슈 / 빌리빌리 등은
**브라우저 세션 쿠키를 파일로 저장**해야 동작합니다.

| 위험 | 설명 |
|---|---|
| **약관 위반** | 대부분 플랫폼이 자동화 접근을 금지합니다 |
| **계정 정지** | 실제로 자주 발생합니다. 도구 공식 문서도 **"부계정을 쓰라"** 고 권합니다 — 이건 위험을 인정하는 문장입니다 |
| **자격증명 노출** | 세션 쿠키가 로컬 파일에 남습니다. 그 쿠키는 사실상 로그인 상태 그 자체입니다 |

**→ 우리 기본 설정: 전부 차단.** (`allow_cookie_channels: false`)

### 4-2. 버전 고정되지 않은 설치

공식 설치 명령이 이렇습니다.

```
pipx install https://github.com/Panniantong/agent-reach/archive/main.zip
```

`main` 브랜치의 **현재 코드**를 그대로 받습니다. 태그나 커밋 고정이 아닙니다.
즉 오늘 안전했던 코드가 내일 바뀔 수 있고, 그 코드는 여러분의 세션 쿠키를 다룹니다.

**→ 공급망 위험입니다.** 우리 설치 스크립트는 이 사실을 설치 전에 경고합니다.

### 4-3. `--system` 플래그

공식 문서는 사용자 승인 후 `--system` 을 붙이라고 안내합니다.
시스템 전역 설정을 바꾸는 옵션입니다.

**→ 우리 설치 스크립트는 `--system` 을 절대 쓰지 않습니다.** 테스트가 이를 강제합니다.

### 4-4. 제3자 서비스 경유

Jina Reader / Exa 등을 경유합니다. 즉 **우리가 무엇을 조회하는지가 제3자에게 전달**됩니다.
리서치 대상 종목이 노출될 수 있다는 뜻입니다. Exa 는 API 키(비용)도 필요합니다.

---

## 5. 우리 통합 원칙

> ### 수집기는 "수집"만 합니다. "판정"은 우리가 합니다.

```
Agent Reach          우리 코드
─────────────        ─────────────────────────────────────
가져온다      →      Research Firewall (스팸·중복·루머·출처없는숫자)
                  →  Tier 판정 (우리 도메인 규칙)
                  →  신뢰도 = min(방화벽 신뢰도, 등급 가중치)
                  →  Agent
```

### 코드로 강제되는 것

| 규칙 | 구현 | 테스트 |
|---|---|---|
| 자동 설치 금지 | 어댑터에 설치 명령 자체가 없음 | `test_never_auto_installs` |
| 쿠키 채널 기본 차단 | `allow_cookie_channels: false` | `test_cookie_channels_blocked_by_default` |
| 수집 문서는 항상 미검증 | `verified=False` 고정 | `test_collected_documents_start_unverified` |
| **레딧은 여전히 Tier E** | 등급은 도메인으로 판정 | `test_reddit_stays_tier_e_regardless_of_collector` |
| 스팸은 수집기 경유해도 차단 | 파이프라인이 방화벽 통과 | `test_spam_is_rejected_even_from_collector` |
| 신뢰도가 등급 상한을 못 넘음 | `min(방화벽, 등급)` | `test_confidence_never_exceeds_tier_weight` |
| 설치 안 돼도 시스템 정상 | `NOT_INSTALLED` 는 오류 아님 | `test_pipeline_survives_missing_collector` |
| `--system` 금지 | 설치 스크립트 검사 | `test_install_script_has_no_system_flag` |

**"Agent Reach 로 가져왔으니 믿을 만하다" 는 이 시스템에서 성립하지 않습니다.**

---

## 6. 설치 방법 (선택)

```powershell
cd C:\ai-research
.\scripts\install-agent-reach.ps1
```

스크립트가 하는 일:
- 위험 4가지를 먼저 화면에 띄우고 **y/N 동의**를 받습니다
- pipx 격리 환경 또는 **프로젝트 전용 venv** 에 설치 (전역 오염 없음)
- `--system` 없이 `agent-reach install --env=auto` 만 실행
- 쿠키 채널은 건드리지 않음
- `agent-reach doctor` 로 진단

옵션:
```powershell
.\scripts\install-agent-reach.ps1 -Method venv    # pipx 없이
.\scripts\install-agent-reach.ps1 -Uninstall      # 제거
```

설치 후 확인: `.\start.ps1` → **Data 화면** 하단 "외부 수집기" 섹션

---

## 7. 쿠키 채널을 켜고 싶다면

권하지 않습니다. 그래도 켜시려면:

```yaml
# config/data_sources/agent_reach.yaml
allow_cookie_channels: true
enabled_channels: [web, rss, youtube, github, twitter]
```

**전에 반드시:**
1. 부계정을 만드세요. 주계정 쿠키는 절대 쓰지 마세요
2. 해당 플랫폼 약관을 직접 확인하세요
3. 계정이 정지될 수 있음을 받아들이세요

우리 시스템 관점에서는 켜든 안 켜든 **Tier E 는 Tier E** 입니다.
트위터에서 가져온 내용은 확정 사실이 될 수 없고, 조사 단서(DISCOVERY_LEAD)로만 쓰입니다.

---

## 8. 라이선스 감사 항목

| 항목 | 내용 |
|---|---|
| Repository | `Panniantong/agent-reach` |
| Version | ⚠️ **고정 안 됨** (`main` 브랜치 zip) |
| License | **MIT** (저장소 페이지 표기. LICENSE 원문은 미확인) |
| 상업 이용 | ✅ (MIT 기준) |
| 수정 시 공개 의무 | ❌ |
| 배포 시 공개 의무 | ❌ |
| 네트워크/SaaS 영향 | 없음 |
| 귀속 표기 | 라이선스 사본 포함 |
| **통합 방식** | 🟡 **별도 프로세스 (CLI 호출)** — 코드 병합 안 함 |

**우리 코드에 병합하지 않습니다.** `subprocess` 로 외부 실행 파일을 부를 뿐입니다.
따라서 라이선스가 나중에 바뀌어도 우리 코드는 영향받지 않으며,
도구를 지워도 시스템은 그대로 돕니다.

**후속 확인 필요**: 실제 사용 전에 LICENSE 원문을 직접 확인하십시오.
저는 이 세션에서 확인하지 못했습니다.

---

## 9. 언제 실제로 쓰게 되나

**Phase 21 (실데이터 수집)** 입니다. 그때 이렇게 씁니다.

```python
from packages.data_connectors import AgentReachCollector, CollectionPipeline

pipe = CollectionPipeline(
    AgentReachCollector(config_dir=settings.config_dir),
    config_dir=settings.config_dir,
)
result = pipe.collect("NVDA 데이터센터 매출", channel="web", limit=10)

result.accepted     # 방화벽 통과 + 등급 판정 완료
result.rejected     # 왜 걸렀는지 사유 포함
result.independent_evidence_count   # ★ 신뢰도 계산에 쓰는 값
result.page_count                   # ★ 쓰면 안 되는 값
```

그때까지는 **설치하지 않아도 아무 문제 없습니다.**

---

## 10. 대안 (Agent Reach 를 안 쓴다면)

| 필요 | 대안 | 라이선스 |
|---|---|---|
| 웹 본문 추출 | `trafilatura` | Apache-2.0 |
| RSS | `feedparser` | BSD |
| 렌더링 필요한 페이지 | `Playwright` | Apache-2.0 |
| SEC 공시 | `edgartools` | MIT |
| 시세 | `yfinance` | Apache-2.0 (데이터는 개인용) |

이쪽이 **의존성은 늘지만 통제는 더 좋습니다.**
Agent Reach 는 "빠르게 넓게" 쪽이고, 위 조합은 "느리지만 정확하게" 쪽입니다.

Phase 21 에서 둘 다 붙여보고 실측으로 정하겠습니다.
어댑터 인터페이스가 같으므로 교체 비용은 낮습니다.
