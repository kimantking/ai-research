# 먼저 읽어주세요 — AI STOCK RESEARCH OFFICE

안녕하세요 antking님. **완성본**입니다. 이 문서 한 장이면 실행됩니다.

---

## 1. 압축 푸는 위치

`C:\ai-research` 폴더 안에 아래처럼 보이면 맞습니다.

```
C:\ai-research\
├─ README_FIRST.md      ← 지금 보고 계신 파일
├─ setup.bat            ← ★ 이걸 더블클릭하면 됩니다
├─ start.bat            ← ★ 그다음 이걸 더블클릭
├─ setup.ps1  start.ps1  stop.ps1  test.ps1 ...
├─ scripts\   packages\   services\   config\   docs\   tests\
```

`C:\ai-research\ai-research\...` 처럼 **두 겹으로 들어가 있으면 안 됩니다.**
안쪽 폴더 내용을 밖으로 꺼내주세요.

---

## 2. 실행 — 가장 확실한 방법

### ★ 파일 탐색기에서 `setup.bat` 더블클릭 → 끝나면 `start.bat` 더블클릭

이게 전부입니다. 브라우저가 자동으로 열립니다.

> **왜 `.bat` 을 권하나요?**
> Windows 는 인터넷에서 받은 `.ps1` 파일의 실행을 기본적으로 막습니다.
> ("이 파일이 디지털 서명되지 않았습니다" 오류가 바로 그것입니다.)
> `.bat` 은 그 제한을 **그 창 하나에서만** 우회합니다. **PC 설정은 바뀌지 않습니다.**

---

## 3. PowerShell 창에서 하고 싶다면

### ★ `.ps1` 이 아니라 `.bat` 을 입력하세요

```powershell
cd C:\ai-research
.\setup.bat
.\start.bat
```

| 입력 | 결과 |
|---|---|
| `.\setup.ps1` | ❌ "디지털 서명되지 않았습니다" 오류 |
| `.\setup.bat` | ✅ 그냥 됩니다 |

`.bat` 은 실행 정책(ExecutionPolicy)의 적용을 받지 않습니다.
그리고 `setup.bat` 이 돌면서 프로젝트 안의 `.ps1` 차단을 풀어주므로,
**그다음부터는 `.\start.ps1` 도 정상 동작합니다.**

### 이 오류를 보셨다면

```
.\setup.ps1 : ... 파일이 디지털 서명되지 않았습니다.
+ CategoryId : 보안 오류 : (:) [], PSSecurityException
```

**정상입니다. 잘못하신 게 아닙니다.** 인터넷에서 받은 파일이라 Windows 가 막은 것뿐입니다.
위처럼 `.\setup.bat` 을 쓰시면 됩니다.

굳이 `.ps1` 로 시작하고 싶으시면 이 한 줄도 됩니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ai-research\scripts\setup.ps1
```

### 그래도 막히면 (실행 정책이 AllSigned 인 경우)

먼저 현재 상태를 확인하세요.

```powershell
Get-ExecutionPolicy -List
```

`CurrentUser` 항목을 아래처럼 바꾸면 해결됩니다.
**내 계정에만 적용되고, 관리자 권한도 필요 없습니다.**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

이게 부담스러우시면 **그냥 `.bat` 더블클릭을 쓰세요.** 결과는 똑같습니다.

---

## 4. 무엇이 꼭 필요한가

| | 필요? | 없으면 |
|---|---|---|
| **Python 3.12** | ✅ **필수** | 실행 불가. [여기서 설치](https://www.python.org/downloads/release/python-3120/) — 설치할 때 **"Add Python to PATH"** 와 **"py launcher"** 를 꼭 체크하세요 |
| Node.js 20+ | ⬜ 선택 | 없어도 됩니다. 백엔드가 픽셀 사무실을 직접 그려줍니다 |
| Docker Desktop | ⬜ 선택 | 없어도 됩니다. MOCK 모드로 동작합니다 |

`setup` 이 **"SETUP 완료 (일부 선택 기능 제외)"** 라고 나오면 **정상**입니다. 그대로 `start` 하세요.

---

## 5. 실행하면 뭐가 보이나요

브라우저에 **픽셀 사무실**이 열립니다.
16명의 에이전트가 21개 공간을 돌아다니며 실제로 일합니다 — 자료 수집, 출처 검증,
Bull/Bear 분리 분석, 토론, 반박, 차트 학습, 시험, 예측 복기, 백테스트, 패턴 발굴.

화면 왼쪽 메뉴 10개를 눌러 안을 들여다보실 수 있습니다.

> ### ⚠️ 화면 오른쪽 위 `MOCK DATA` 배지를 꼭 봐주세요
> **지금 데이터는 전부 합성(가짜)입니다.** 화면의 수익률·승률은 **실제 시장과 아무 관계가 없습니다.**
> 절대로 투자 판단에 쓰지 마세요. 이 배지는 끌 수 없게 만들어 두었습니다.
> 실제 시장 데이터 연결은 다음 단계(Phase 21)입니다.

---

## 6. 자주 쓰는 명령

| 하고 싶은 일 | 더블클릭 | PowerShell |
|---|---|---|
| 처음 준비 | `setup.bat` | `.\setup.ps1` |
| 실행 | `start.bat` | `.\start.ps1` |
| 종료 | `stop.bat` | `.\stop.ps1` |
| 상태 확인 | `health.bat` | `.\health.ps1` |
| 테스트 전부 돌리기 | `test.bat` | `.\test.ps1` |
| 환경 점검 (읽기만 함) | — | `.\audit.ps1` |

---

## 7. 지금 상태 — 정직하게

**되는 것:** 단위 테스트 187개 통과 / 인수 테스트 66개 통과 / 화면 10개 콘솔 에러 0

**아직 안 되는 것:**

| 제한 | 뜻 |
|---|---|
| 데이터가 전부 합성 | 성과 수치는 **실전과 무관** |
| LLM 미연결 | 토론이 규칙 기반. 진짜 추론엔 API 키 필요 (**비용 발생 — 그래서 임의로 안 했습니다**) |
| DB 미연결 | 껐다 켜면 학습 기록 초기화 |
| Next.js 화면 미검증 | 개발 환경에서 npm 접근이 막혀 빌드 확인 못 함 |
| Pattern Miner 다중검정 미보정 | **현재 가장 큰 통계적 약점** |

전체 목록은 `PROJECT_STATUS.md` 5번에 있습니다.

---

## 8. 막혔을 때

1. `docs\TROUBLESHOOTING.md` — 흔한 오류 모음
2. 그래도 안 되면 **오류 화면을 그대로 저에게 붙여넣어 주세요.** 제가 고치겠습니다.

---

## 9. 문서 읽는 순서 (시간 없으시면 굵은 것만)

1. **`PROJECT_STATUS.md`** ← 현재 상태 한눈에. 이것만 봐도 됩니다
2. `docs\DECISIONS.md` ← 왜 그렇게 만들었는지 결정 29개
3. `docs\SECURITY.md` ← 안전장치
4. `docs\LICENSE_AUDIT.md` ← 법적 위험 (OpenBB·vectorbt·nautilus 배제 이유)
5. `docs\ARCHITECTURE.md` ← 상세 설계 (가장 깁니다)

---

## 10. 더 편한 방법

**Claude 데스크톱 앱**에서 이 작업을 열고 **"이 컴퓨터에 연결"** 을 선택하시면,
제가 antking님 PC 에서 직접 실행하고 직접 고칠 수 있습니다.

(그 선택지가 안 보이면, 데스크톱 앱에서 컴퓨터를 지정해 **새 작업**을 시작하시면 됩니다.)
