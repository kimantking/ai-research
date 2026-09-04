# SECURITY

---

## 1. 시크릿 관리

| 항목 | 처리 |
|---|---|
| `.env` | **Git 제외** (`.gitignore` 최상단). 테스트가 검증 |
| `.env.example` | 커밋됨. **키 값은 전부 비어 있음** — 테스트가 검증 |
| 시크릿 읽기 | `packages/shared/config.py` **한 곳에서만**. 코드 곳곳에서 `os.environ` 직접 읽지 않음 |
| 상태 공개 | `Settings.public_dict()` 는 시크릿을 **절대 담지 않음** — 테스트가 검증 |

---

## 2. 로그 마스킹

API 키가 실수로 로그에 들어가도 출력에는 `***` 로만 남습니다.

```python
mask_text("key sk-abcdef123456 end")   # → "key *** end"
mask_event({"api_key": "supersecret"}) # → {"api_key": "***"}
```

마스킹 대상:
- `sk-` 로 시작하는 토큰
- `Bearer <token>`
- `api_key=`, `token=`, `secret=`, `password=` 뒤의 값
- 키 이름이 시크릿류인 필드 (`database_url`, `redis_url` 포함)

structlog 프로세서 체인에서 **렌더러 앞**에 배치됩니다.
structlog 이 없으면 표준 logging 폴백이 같은 마스킹을 합니다.

---

## 3. 입력 검증

| 엔드포인트 | 검증 |
|---|---|
| `POST /api/research` | 티커 길이 ≤ 12, 영숫자·`.`·`-` 만 |
| `POST /api/backtest` | 전략 화이트리스트, 수수료·슬리피지 0~500bp |
| `GET /api/patterns` | horizon ∈ {1, 5, 20} |
| 정적 파일 | **경로 탈출 차단** (`/static/../../.env` → 403) |

경로 탈출 차단은 실제로 테스트했습니다:
```
curl --path-as-is /static/../../.env  →  403 {"error": "허용되지 않은 경로"}
```

---

## 4. 네트워크

- 기본 바인딩: **`127.0.0.1` 만**. 외부에 노출되지 않습니다
- CORS: 로컬 프론트엔드 포트만 허용
- 외부 공개 배포는 **사용자 승인 필요** 항목입니다

---

## 5. 스크립트 안전장치

`tests/test_scripts_safety.py` 가 PowerShell 스크립트 20개를 검사합니다.

**금지 명령이 하나라도 있으면 테스트가 실패합니다:**

```
docker system prune / volume prune / container prune / image prune / network prune
docker stop $(...)  / docker kill $(...)
Set-ExecutionPolicy (CurrentUser 범위 아닌 것)
[Environment]::SetEnvironmentVariable(..., Machine)
Uninstall-*
npm install -g
```

**추가 검사:**
- `docker compose` 는 반드시 `-p ai-stock-research-office` 로 범위 지정
- `down -v` (볼륨 삭제)는 `reset-local.ps1` 에서만, **확인 프롬프트 필수**
- `Remove-Item -Recurse` 는 **경로 탈출 검사(`StartsWith`)와 함께**만 허용
- `stop.ps1` 은 프로세스 화이트리스트(`python`, `node`)만 종료
- bash 전용 문법(`rm -rf`, `source .../activate`, `export VAR=`) 금지

### 삭제 안전장치

```powershell
function Assert-InsideProject([string]$Path) {
    # 프로젝트 폴더 밖이면 예외
    # 프로젝트 루트 자체를 지우려 해도 예외
}
```

다른 프로젝트를 건드리는 사고는 대부분 경로 조립 실수에서 나옵니다.

---

## 6. 의존성 감사

`.\scripts\license-check.ps1` 이 Python·Node 의존성을 스캔합니다.

**탐지 대상:** AGPL, GPL-2/3, SSPL, Commons Clause, BUSL, Elastic License
발견 시 종료 코드 1 → CI 에서 빌드 실패

간접 의존성으로 AGPL 패키지가 들어오는 사고가 실제로 자주 발생합니다.
사람이 매번 확인할 수 없으니 스크립트로 막습니다.

---

## 7. 아직 없는 것

| 항목 | 언제 |
|---|---|
| 인증/인가 | 다중 사용자가 생기면 |
| Rate Limiting | 외부 노출 시 |
| DB 접속 암호화 | Phase 5 |
| 감사 로그 서명 | 필요 시 |
| SBOM 생성 | Phase 22 |

현재는 **로컬 단일 사용자 전제**입니다. 외부에 노출하기 전에 위 항목이 필요합니다.
