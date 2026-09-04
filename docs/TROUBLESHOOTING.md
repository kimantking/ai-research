# TROUBLESHOOTING

---

## ★ 가장 많이 만나는 오류 — "디지털 서명되지 않았습니다"

```
.\setup.ps1 : C:\ai-research\setup.ps1 파일을 로드할 수 없습니다.
              ... 파일이 디지털 서명되지 않았습니다.
+ CategoryInfo : 보안 오류 : (:) [], PSSecurityException
+ FullyQualifiedErrorId : UnauthorizedAccess
```

### 원인

**잘못하신 게 없습니다.** Windows 는 인터넷에서 받은 파일에 "외부에서 왔음" 표시
(Mark of the Web)를 붙입니다. PowerShell 실행 정책이 `RemoteSigned` 또는 `AllSigned`
이면 그 표시가 붙은 `.ps1` 을 서명 없이는 실행하지 않습니다.

### 해결 1 — 가장 쉬움 (권장)

**`.ps1` 대신 `.bat` 을 실행하세요.** `.bat` 은 실행 정책의 적용을 받지 않습니다.

파일 탐색기에서 `setup.bat` 더블클릭 → `start.bat` 더블클릭.

**지금 열린 PowerShell 창에서 그대로 하셔도 됩니다:**

```powershell
cd C:\ai-research
.\setup.bat
.\start.bat
```

| 입력 | 결과 |
|---|---|
| `.\setup.ps1` | ❌ PSSecurityException |
| `.\setup.bat` | ✅ 실행됨 |

`setup.bat` 이 프로젝트 안의 `.ps1` 차단을 풀어주므로,
**그다음부터는 `.\start.ps1` 도 정상 동작합니다.**
PC 의 실행 정책은 바뀌지 않습니다.

> **더블클릭했더니 "Windows에서 PC를 보호했습니다" 파란 창이 뜬다면?**
> 인터넷에서 받은 `.bat` 이라 SmartScreen 이 한 번 확인하는 것입니다.
> **추가 정보 → 실행** 을 누르시면 됩니다. 이 창이 싫으시면 위처럼
> PowerShell 에서 `.\setup.bat` 으로 실행하세요 (이 경로로는 뜨지 않습니다).

### 해결 2 — PowerShell 에서 한 줄

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ai-research\scripts\setup.ps1
```

이 `setup` 이 프로젝트 폴더 안의 스크립트 차단을 스스로 풀어줍니다(0/7 단계).
**한 번만 하면** 그다음부터는 `cd C:\ai-research` → `.\start.ps1` 이 그냥 됩니다.

### 해결 3 — 차단 표시만 직접 제거

```powershell
Get-ChildItem -Path C:\ai-research -Recurse -Include *.ps1,*.bat | Unblock-File
```

파일 하나하나의 "외부에서 왔음" 표시만 지웁니다. 실행 정책은 그대로입니다.

### 해결 3 을 해도 안 되면 — 실행 정책이 `AllSigned`

`AllSigned` 는 로컬에서 만든 스크립트까지 서명을 요구합니다. 확인:

```powershell
Get-ExecutionPolicy -List
```

`CurrentUser` 를 바꾸세요. **내 계정에만 적용되고 관리자 권한이 필요 없습니다.**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

되돌리려면 `-ExecutionPolicy Undefined` 로 다시 실행하시면 됩니다.

> 회사 PC 처럼 그룹 정책(`MachinePolicy` / `UserPolicy`)으로 강제된 경우에는
> 위 명령이 무시됩니다. 그때는 **해결 1(`.bat` 더블클릭)** 을 쓰세요.

---

## "예기치 않은 토큰입니다" / ParserError

```
식 또는 문에서 예기치 않은 '3.12嫄' 토큰입니다.
+ FullyQualifiedErrorId : UnexpectedToken
```

한글이 깨진 토큰(`嫄` 같은 글자)이 보이면 **파일 인코딩 문제**입니다.

Windows PowerShell 5.1 은 BOM 이 없는 `.ps1` 을 UTF-8 이 아니라 CP949 로 읽습니다.
한글 바이트가 어긋나면서 줄바꿈까지 삼켜 코드가 주석 안으로 들어갑니다.

**해결:** 이 버전은 모든 `.ps1` 이 **UTF-8 BOM + CRLF** 로 저장되어 있어 발생하지 않습니다.
그래도 난다면 **오래된 zip** 입니다. 최신 파일로 다시 받으세요.

확인 방법 (앞 3바이트가 `239 187 191` 이면 정상):

```powershell
[byte[]](Get-Content C:\ai-research\scripts\setup.ps1 -Encoding Byte -TotalCount 3)
```

> ⚠️ 스크립트를 직접 수정하실 때는 **"UTF-8 (BOM 포함)"** 으로 저장하세요.
> VS Code 오른쪽 아래 인코딩 표시를 눌러 `Save with Encoding` → `UTF-8 with BOM`.
> 메모장은 "UTF-8(BOM)" 을 고르시면 됩니다.

---

## `cd C:\ai-research` 에서 "경로가 존재하지 않습니다"

압축이 아직 안 풀렸거나, 다른 위치에 풀렸거나, **두 겹**으로 들어갔습니다.

```powershell
dir C:\ai-research
```

`setup.ps1`, `scripts`, `packages` 가 바로 보여야 합니다.
`C:\ai-research\ai-research\...` 처럼 되어 있으면 안쪽 폴더 내용을 밖으로 꺼내세요.

---

## 화면이 안 뜹니다

### 1) 백엔드가 살아 있는지 확인

```powershell
.\health.ps1
```

`Backend API` 가 `DOWN` 이면 백엔드 창의 오류 메시지를 보세요.

### 2) 주소 확인

- Node 를 설치하셨으면: `http://localhost:3010`
- Node 없이 백엔드만 도는 중이면: `http://localhost:8010`

포트가 바뀌었을 수 있습니다. `.env` 의 `API_PORT` / `WEB_PORT` 를 확인하세요.

### 3) 브라우저 캐시

`Ctrl + Shift + R` 로 강제 새로고침.

---

## `.venv` 관련 오류

### "가상환경이 없습니다"

```powershell
.\setup.ps1
```

### ".venv 가 손상되어 있습니다"

`setup.ps1` 이 **이 프로젝트의 .venv 만** 다시 만듭니다.
다른 프로젝트의 가상환경은 건드리지 않습니다 (경로 안전장치가 막습니다).

### "Python 3.12를 찾지 못했습니다"

```powershell
py -0p          # 설치된 Python 목록 확인
py -3.12 -V     # 3.12 가 있는지 확인
```

없으면 https://www.python.org/downloads/release/python-3120/ 에서 설치.
설치 시 **Add Python to PATH** 와 **py launcher** 체크 필수.

---

## 패키지 설치가 실패합니다

**괜찮습니다. 그래도 돌아갑니다.**

`start.ps1` 이 FastAPI 설치 여부를 확인하고, 없으면 **standalone 모드**로 실행합니다.
standalone 은 파이썬 표준 기능만 쓰므로 설치가 필요 없습니다.

```
[주의] FastAPI 가 설치되어 있지 않습니다 → standalone 모드로 실행합니다
       (외부 패키지 없이 파이썬 표준 기능만으로 동작합니다. 화면은 동일합니다)
```

두 서버는 같은 로직(`routes.py`)을 쓰므로 **응답이 다를 수 없습니다.**

---

## PowerShell 실행 정책

→ `docs/WINDOWS_SETUP.md` 4번

가장 쉬운 해결: `start.bat` 더블클릭

---

## 포트 충돌

```powershell
.\health.ps1     # 어떤 프로세스가 쓰는지 표시
```

`.env` 에서 숫자만 바꾸고 재시작하면 됩니다.

```
API_PORT=8011
WEB_PORT=3011
```

**다른 프로젝트를 끄지 마세요.** 우리가 비켜가는 것이 이 프로젝트의 원칙입니다.

---

## Docker 오류

### "Docker가 실행 중이 아닙니다"

지금 단계에서는 **없어도 됩니다.** MOCK 모드로 정상 동작합니다.

Docker 를 쓰려면 Docker Desktop 을 켜고 다시 실행하세요.

### 컨테이너가 안 뜹니다

```powershell
.\logs.ps1 -Docker
```

이 프로젝트 컨테이너(`airo-*`)의 로그만 봅니다.

---

## 캐릭터가 안 움직입니다

### 1) 실시간 연결 확인

상단 바의 배지를 보세요.

- 🟢 `실시간 연결됨` — 정상
- 🔴 `연결 끊김 · 재시도` — WebSocket 이 끊김. 백엔드 확인

### 2) 백엔드가 도는데도 안 움직인다면

**정상일 수 있습니다.** 프론트엔드는 상태를 지어내지 않습니다.
백엔드에서 이벤트가 나가야만 움직입니다.

Audit 화면 → 최근 이벤트에 `agent.status_changed` 가 쌓이는지 확인하세요.

---

## 테스트가 실패합니다

```powershell
.\test.ps1
```

특정 테스트만:

```powershell
.\test.ps1 -Filter tests.test_point_in_time
```

### 자주 나오는 것

`agent_step_failed ... error=의도적 실패` 라는 ERROR 로그가 보이는데
테스트는 OK 인 경우 → **정상입니다.**
"에이전트 한 명이 넘어져도 사무실이 멈추지 않는다"를 검증하는 테스트가
일부러 예외를 던지는 것입니다.

---

## 학습 점수가 50% 근처입니다

**정상입니다.**

현재는 합성(MOCK) 데이터이고, 여기에는 예측 가능한 신호가 거의 없습니다.
시스템이 "80% 맞춥니다"라고 하지 않는 것이 오히려 정직하다는 증거입니다.

학습 기계 자체는 작동합니다 — 일부러 학습 가능한 신호를 주면 85% 이상 나옵니다
(`test_model_learns_a_learnable_signal`).

---

## 패턴 승률이 너무 높게 나옵니다

Pattern 화면 맨 위의 경고를 읽어주세요.

합성 데이터 생성기에 **의도적으로 완만한 사이클**이 들어 있어서
모멘텀 조건이 잘 맞습니다. 실제 시장의 우위를 전혀 의미하지 않습니다.

---

## 리포트가 "차단됨" 으로 나옵니다

**정상 동작입니다.**

Evidence Gate 가 근거 ID 없는 수치를 발견하면 리포트를 발행하지 않습니다.
어떤 문장이 문제인지 화면에 표시됩니다.

---

## 완전히 처음부터 다시

```powershell
.\scripts\reset-local.ps1     # y/N 확인 후 진행
.\setup.ps1
.\start.ps1
```

---

## 그래도 안 되면

1. `.\scripts\audit.ps1` 실행
2. `scripts\audit-report.txt` 내용 확인
3. 백엔드 창의 오류 메시지 확인
4. `.\logs.ps1` 확인

이 네 가지 정보가 있으면 원인을 거의 특정할 수 있습니다.

---

## 백엔드가 안 뜹니다 — "백엔드 응답을 확인하지 못했습니다"

`start` 는 성공했다고 하는데 브라우저가 안 열리거나 화면이 비어 있는 경우입니다.

### 1) 백엔드 창을 보세요

`start` 는 백엔드를 **별도 창**에서 띄웁니다. 그 창에 오류가 그대로 남아 있습니다.
창은 자동으로 닫히지 않으므로, 위로 스크롤해서 빨간 글씨를 찾아보세요.

정상이면 창 맨 위가 이렇게 나옵니다.

```
=============================================================
  AI STOCK RESEARCH OFFICE  -  백엔드
  이 창을 닫지 마세요. 닫으면 시스템이 멈춥니다.

  브라우저 주소 :  http://localhost:8010
=============================================================

2026-09-04 06:24:51 INFO  persistence_ready path=C:\ai-research\data\airo.db
2026-09-04 06:24:51 INFO  server_ready url=http://127.0.0.1:8010 agents_total=177
```

### 2) 직접 띄워서 오류를 눈으로 보기

가장 확실한 방법입니다. **오류가 이 창에 그대로 나옵니다.**

```powershell
cd C:\ai-research
$env:PYTHONPATH = "C:\ai-research"
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8010
```

FastAPI 가 없다면 (같은 화면이 나옵니다):

```powershell
.\.venv\Scripts\python.exe -m services.api.standalone --port 8010
```

`Application startup complete` 또는 `server_ready` 가 보이면 정상입니다.
그 상태로 브라우저에서 `http://localhost:8010` 을 여세요.

### 3) 포트가 이미 쓰이는 중일 때

```powershell
.\stop.bat
.\start.bat
```

`stop` 은 **이 프로젝트가 띄운 것만** 끕니다. 다른 프로그램은 건드리지 않습니다.

### 4) Docker "port is already allocated" 는 무시하셔도 됩니다

**Docker 는 이제 쓰지 않습니다.** 학습·시세는 `data\airo.db` (SQLite) 에 저장됩니다.
그래서 컨테이너를 기본으로 띄우지 않습니다. 굳이 띄우시려면:

```powershell
.\start.ps1 -WithDocker
```
