# WINDOWS SETUP

---

## 1. 가장 빠른 길

```powershell
cd C:\ai-research
.\setup.ps1
.\start.ps1
```

끝입니다. 브라우저가 자동으로 열립니다.

---

## 2. 그 전에 — 환경 점검 (선택, 읽기 전용)

```powershell
cd C:\ai-research\scripts
powershell -ExecutionPolicy Bypass -File .\audit.ps1
```

이 스크립트는 **아무것도 설치하거나 삭제하지 않습니다.** 읽기만 합니다.

점검 항목: Windows / PowerShell / ExecutionPolicy / Git /
Python 런처 / Python 3.12 / 프로젝트 .venv / Node / npm /
Docker / 실행 중인 컨테이너 / 포트 10개 / 디스크 / 쓰기 권한

결과는 `scripts\audit-report.txt` 에 저장됩니다.

### 중요한 구분

Python 3.12 가 PC 에 있는데 `C:\ai-research\.venv` 가 깨진 경우,
스크립트는 이렇게 구분해서 보고합니다:

```
[OK   ] Python 3.12 (global)      3.12.x
[ERROR] Project .venv             BROKEN - Scripts\python.exe 누락
```

"Python 없음" 이라고 하지 않습니다.

---

## 3. 필요한 것

| | 필수? | 없으면 |
|---|---|---|
| **Python 3.12** | ✅ 필수 | setup 이 중단됩니다 |
| Git | 권장 | 커밋만 안 됩니다 |
| Node.js 20+ | ❌ 선택 | **픽셀 사무실은 그대로 뜹니다** (백엔드가 직접 서빙) |
| Docker Desktop | ❌ 선택 | MOCK 모드로 동작. Phase 11 실데이터부터 필요 |

### Python 3.12 설치

https://www.python.org/downloads/release/python-3120/

설치 시 반드시 체크:
- ☑ **Add Python to PATH**
- ☑ **py launcher**

---

## 4. PowerShell 실행이 막힐 때

증상: `이 시스템에서 스크립트를 실행할 수 없으므로...`

### 방법 A — .bat 파일 더블클릭 (가장 쉬움)

`setup.bat`, `start.bat`, `stop.bat` 이 준비되어 있습니다.
이 파일들은 실행 정책을 우회하되, **그 명령 한 번에만** 적용됩니다.

### 방법 B — 현재 사용자에게만 허용

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`-Scope CurrentUser` 가 중요합니다. **시스템 전체를 바꾸지 않습니다.**

### 방법 C — 한 번만 우회

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

---

## 5. npm 이 막힐 때

`npm.ps1` 이 실행 정책에 걸리는 경우가 있습니다.
스크립트가 자동으로 `npm.cmd` 를 우선 시도합니다.

그래도 안 되면 방법 B 를 쓰시거나, **Node 없이 그냥 진행하셔도 됩니다.**
`start.ps1` 이 Node 가 없으면 백엔드만 띄우고, 픽셀 사무실은 정상 동작합니다.

---

## 6. 포트가 겹칠 때

**아무것도 안 하셔도 됩니다.**

`setup.ps1` 이 포트를 검사하고, 사용 중이면 **우리가 비켜갑니다.**

```
[주의] PostgreSQL: 포트 5433 이 'postgres' 에 의해 사용 중 → 5434 으로 변경했습니다
```

다른 프로젝트를 절대 종료시키지 않습니다.

직접 바꾸고 싶으면 `.env` 의 숫자만 고치면 됩니다.

---

## 7. Docker 없이 쓰기

지금 단계(픽셀 사무실 · 학습 · 백테스트 · 패턴)에서는 **Docker 가 전혀 필요 없습니다.**

```powershell
.\start.ps1 -NoDocker
```

Docker 는 Phase 11(실제 데이터 저장)부터 필요합니다.

---

## 8. 설치되는 것 / 안 되는 것

### 설치됨 (프로젝트 폴더 안에만)
- `C:\ai-research\.venv` — Python 가상환경
- `C:\ai-research\apps\web\node_modules` — Node 패키지 (선택)

### 절대 건드리지 않음
- 시스템 전역 Python / Node
- 다른 프로젝트의 `.venv` / `node_modules`
- 다른 프로젝트의 Docker 컨테이너 / 볼륨
- 시스템 환경변수
- 다른 프로젝트가 쓰는 포트

---

## 9. 완전 초기화

```powershell
.\scripts\reset-local.ps1
```

**y/N 확인 프롬프트가 뜹니다.** 삭제 대상을 먼저 보여줍니다.

지우는 것: 이 프로젝트의 `.venv`, `node_modules`, `.next`
지우지 않는 것: `.env` (설정 보존), 다른 모든 것

옵션:
- `-IncludeData` — `data\`, `logs\` 도 삭제
- `-IncludeVolumes` — 이 프로젝트 Docker 볼륨도 삭제

---

## 10. 명령 요약

```powershell
.\setup.ps1        # 처음 한 번
.\start.ps1        # 실행
.\stop.ps1         # 종료
.\restart.ps1      # 재시작
.\health.ps1       # 상태 확인
.\test.ps1         # 테스트
.\update.ps1       # 패키지 최신화
.\logs.ps1         # 로그
```
