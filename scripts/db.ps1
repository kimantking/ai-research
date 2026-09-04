<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  DB (학습 저장소)
=============================================================
 에이전트가 배운 것이 어디에 얼마나 저장돼 있는지 봅니다.

 이 스크립트가 하는 일:
   - 저장소 상태 조회 (읽기 전용)
   - -Save : 지금 즉시 저장
   - -Backup : 저장 파일을 복사해 백업

 이 스크립트가 절대 하지 않는 일:
   - 저장소 삭제 (초기화는 .\reset-local.ps1 에만 있습니다)
   - 다른 프로젝트의 DB 접근

 사용법:
   .\scripts\db.ps1
   .\scripts\db.ps1 -Save
   .\scripts\db.ps1 -Backup
=============================================================
#>
param(
    [switch]$Save,
    [switch]$Backup
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

$envPath = Join-Path $ProjectRoot '.env'
$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
$base    = "http://localhost:$apiPort"

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  학습 저장소 (영속화)" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# --- 백업은 서버 없이도 됩니다 ---
if ($Backup) {
    $dbRel = Get-EnvValue $envPath 'SQLITE_PATH' 'data/airo.db'
    $dbPath = Join-Path $ProjectRoot ($dbRel -replace '/', '\')
    if (-not (Test-Path $dbPath)) {
        Write-Warn2 "저장 파일이 아직 없습니다: $dbPath"
        exit 0
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupDir = Join-Path $ProjectRoot 'data\backup'
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
    $dest = Join-Path $backupDir "airo-$stamp.db"
    Assert-InsideProject $dest | Out-Null
    Copy-Item $dbPath $dest
    Write-Ok "백업 완료: $dest"
    Write-Info "복원하려면 이 파일을 $dbPath 로 되돌려 놓으면 됩니다."
    exit 0
}

# --- 학습만 초기화 (백엔드를 먼저 꺼야 합니다) ---
if ($ResetLearning) {
    $dbRel  = Get-EnvValue $envPath 'SQLITE_PATH' 'data/airo.db'
    $dbPath = Join-Path $ProjectRoot ($dbRel -replace '/', '\\')
    if (-not (Test-Path $dbPath)) {
        Write-Warn2 "저장 파일이 없습니다: $dbPath  (초기화할 것이 없습니다)"
        exit 0
    }

    # 백엔드가 살아 있으면 메모리 상태가 다시 저장돼 초기화가 되돌아갑니다.
    $running = $false
    try {
        $r = Invoke-WebRequest -Uri "$base/health" -TimeoutSec 3 -UseBasicParsing
        $running = ($r.StatusCode -eq 200)
    } catch { }
    if ($running) {
        Write-Err "백엔드가 실행 중입니다. 먼저 꺼주세요."
        Write-Info "  .\stop.bat  을 실행한 뒤 다시 시도하세요."
        Write-Info "  (켜진 상태로 지우면 메모리에 있던 학습이 곧바로 다시 저장됩니다)"
        exit 1
    }

    Write-Host ""
    Write-Warn2 "합성 데이터로 배운 것을 지웁니다."
    Write-Host "  지웁니다 : 모델 가중치, 학습시간, 예측 저널, 지식, 이벤트" -ForegroundColor White
    Write-Host "  남깁니다 : 실제 시세(bars), PIT 사실(facts), data\market\ 의 CSV" -ForegroundColor White
    Write-Host ""
    Write-Host "  왜 하는가: 합성 캔들 생성기에는 의도적인 사이클이 들어 있습니다." -ForegroundColor DarkGray
    Write-Host "  그 위에서 배운 가중치를 그대로 두면, 실데이터로 넘어가도" -ForegroundColor DarkGray
    Write-Host "  '없는 규칙'을 이미 믿는 상태에서 시작하게 됩니다." -ForegroundColor DarkGray
    Write-Host ""
    $ans = Read-Host "  진행할까요? (y/N)"
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Write-Info "취소했습니다. 아무것도 지우지 않았습니다."
        exit 0
    }

    # 지우기 전에 항상 백업합니다.
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupDir = Join-Path $ProjectRoot 'data\backup'
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
    $dest = Join-Path $backupDir "airo-before-reset-$stamp.db"
    Assert-InsideProject $dest | Out-Null
    Copy-Item $dbPath $dest
    Write-Ok "백업 완료: $dest"

    $venvPy = Get-VenvPython
    $code = "import json,sys; sys.path.insert(0, r'$ProjectRoot'); " +
            "from packages.persistence import SqliteStore; " +
            "s = SqliteStore(r'$dbPath'); print(json.dumps(s.reset_learning(), ensure_ascii=False)); s.close()"
    $out = & $venvPy -c $code
    if ($LASTEXITCODE -ne 0) {
        Write-Err "초기화 실패. 백업 파일은 그대로 있습니다: $dest"
        exit 1
    }
    Write-Ok "학습 기록을 지웠습니다"
    Write-Info $out
    Write-Host ""
    Write-Info "이제 .\start.bat 으로 실행하면 실제 데이터 위에서 처음부터 배웁니다."
    Write-Host ""
    exit 0
}

# --- 나머지는 백엔드가 필요합니다 ---
$alive = $false
try {
    $r = Invoke-WebRequest -Uri "$base/health" -TimeoutSec 3 -UseBasicParsing
    $alive = ($r.StatusCode -eq 200)
} catch { }
if (-not $alive) {
    Write-Warn2 "백엔드가 꺼져 있습니다 ($base)"
    Write-Info "상태 조회에는 백엔드가 필요합니다. .\start.bat 을 먼저 실행하세요."
    Write-Info "백업만 하려면:  .\scripts\db.ps1 -Backup"
    exit 0
}

if ($Save) {
    try {
        $res = Invoke-RestMethod -Uri "$base/api/persistence/save" -Method Post -TimeoutSec 60
        if ($res.saved) {
            Write-Ok "저장 완료 - 에이전트 $($res.agents_saved)명 / 예측 $($res.predictions_saved)건"
        } else {
            Write-Warn2 "저장하지 못했습니다: $($res.error) $($res.reason)"
        }
    } catch {
        Write-Err "저장 요청 실패: $_"
        exit 1
    }
    Write-Host ""
}

try {
    $st = Invoke-RestMethod -Uri "$base/api/persistence" -TimeoutSec 10
} catch {
    Write-Err "상태 조회 실패: $_"
    exit 1
}

if (-not $st.enabled) {
    Write-Warn2 "영속화가 꺼져 있습니다."
    Write-Info $st.warning
    Write-Info ".env 에서 PERSISTENCE=sqlite 로 두면 켜집니다."
    exit 0
}

Write-Ok "백엔드: $($st.store.backend) / 스키마 v$($st.store.schema_version)"
Write-Info "파일: $($st.store.path)  ($([math]::Round($st.store.size_bytes/1KB)) KB)"
Write-Host ""
Write-Host "  저장된 행" -ForegroundColor White
$st.store.rows.PSObject.Properties | ForEach-Object {
    Write-Host ("    {0,-14} {1}" -f $_.Name, $_.Value) -ForegroundColor Gray
}
Write-Host ""
Write-Info $st.restore.note
if ($st.last_save -and $st.last_save.saved) {
    Write-Info "마지막 저장: 에이전트 $($st.last_save.agents_saved)명 / 예측 $($st.last_save.predictions_saved)건"
}
Write-Host ""
Write-Info "백업:  .\scripts\db.ps1 -Backup"
Write-Host ""
