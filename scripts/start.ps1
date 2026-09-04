<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  START
=============================================================
 백엔드를 새 창에서 띄우고 브라우저를 엽니다.
 (Next.js 패키지가 설치돼 있으면 프론트엔드도 함께 띄웁니다)

 Docker 는 필요 없습니다. 학습·시세는 SQLite(data\airo.db) 에 저장됩니다.

 사용법:
   cd C:\ai-research
   .\start.ps1
   .\start.ps1 -WithDocker    PostgreSQL/Valkey 컨테이너도 띄움 (선택)
   .\start.ps1 -NoBrowser     브라우저를 열지 않음
=============================================================
#>
param(
    [switch]$NoBrowser,     # 브라우저 자동 열기 안 함
    [switch]$WithDocker,    # PostgreSQL/Valkey 컨테이너도 띄움 (지금은 불필요)
    [switch]$NoDocker       # (구버전 호환. 지금은 '띄우지 않음' 이 기본입니다)
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

$envPath = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envPath)) {
    Write-Err ".env 파일이 없습니다. 먼저 .\setup.ps1 을 실행하세요."
    exit 1
}
if (-not (Test-VenvHealthy)) {
    Write-Err "가상환경(.venv)이 준비되지 않았습니다. 먼저 .\setup.ps1 을 실행하세요."
    exit 1
}

$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
$webPort = Get-EnvValue $envPath 'WEB_PORT' '3010'
$venvPy  = Get-VenvPython

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  AI STOCK RESEARCH OFFICE  -  START" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# -------------------------------------------------------------
Write-Step "1/3  데이터베이스 (선택)"
# -------------------------------------------------------------
# ★ 학습·시세 저장은 SQLite(data\airo.db) 로 합니다. Docker 는 필요 없습니다.
#   예전에는 기본으로 컨테이너를 띄우려다 포트가 겹치면 빨간 오류가 떴는데,
#   정작 그 컨테이너를 쓰지도 않았습니다. 이제는 요청할 때만 띄웁니다.
if ($WithDocker -and -not $NoDocker) {
    if (Test-DockerRunning) {
        Write-Info "PostgreSQL / Valkey 컨테이너를 시작합니다 (이 프로젝트 것만)..."
        Push-Location $ProjectRoot
        try {
            docker compose -p $ComposeProject up -d
            if ($LASTEXITCODE -eq 0) { Write-Ok "컨테이너 시작됨 (airo-postgres, airo-redis)" }
            else { Write-Warn2 "컨테이너 시작 실패 - 그래도 시스템은 정상 동작합니다" }
        } finally { Pop-Location }
    } else {
        Write-Warn2 "Docker 가 실행 중이 아닙니다 - 건너뜁니다 (문제 없음)"
    }
} else {
    Write-Info "Docker 는 사용하지 않습니다. 학습·시세는 SQLite 에 저장됩니다."
    Write-Info "(굳이 컨테이너를 띄우시려면:  .\start.ps1 -WithDocker)"
}

# -------------------------------------------------------------
Write-Step "2/3  백엔드 API 시작 (포트 $apiPort)"
# -------------------------------------------------------------
# FastAPI 모드일 때만 /docs (Swagger) 가 존재합니다.
# standalone 모드에는 없으므로, 없는 주소를 안내하지 않도록 여기서 구분합니다.
$hasSwagger = $false

if (-not (Test-PortFree ([int]$apiPort))) {
    $owner = Get-PortOwner ([int]$apiPort)
    Write-Warn2 "포트 $apiPort 이 이미 사용 중입니다 (프로세스: $owner)"
    Write-Info "이미 백엔드가 떠 있는 것일 수 있습니다. 그대로 진행합니다."
} else {
    # FastAPI 가 설치되어 있으면 그걸 쓰고, 없으면 표준 라이브러리 서버로 돌립니다.
    # 두 서버는 같은 로직(routes.py)을 쓰므로 화면과 응답은 동일합니다.
    & $venvPy -c "import fastapi, uvicorn" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "FastAPI 모드로 실행합니다"
        $hasSwagger = $true
        $mode = 'fastapi'
    } else {
        Write-Warn2 "FastAPI 가 설치되어 있지 않습니다 - standalone 모드로 실행합니다"
        Write-Info "(외부 패키지 없이 파이썬 표준 기능만으로 동작합니다. 화면은 동일합니다)"
        $mode = 'standalone'
    }

    # ★ 긴 명령 문자열을 -Command 로 넘기지 않습니다.
    #   따옴표·세미콜론·괄호·한글이 섞인 문자열이 새 창으로 전달되는 도중
    #   깨져서 백엔드가 아예 뜨지 않는 일이 실제로 있었습니다.
    #   실행기 파일에 단순한 인자만 넘기면 그 문제가 원천적으로 사라집니다.
    $launcher = Join-Path $PSScriptRoot '_run-backend.ps1'
    if (-not (Test-Path $launcher)) {
        Write-Err "백엔드 실행기를 찾을 수 없습니다: $launcher"
        Write-Info "압축을 다시 풀었는지 확인하세요."
        exit 1
    }
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $launcher,
        '-ProjectPath', $ProjectRoot,
        '-PythonExe', $venvPy,
        '-Port', $apiPort,
        '-Mode', $mode
    ) -WorkingDirectory $ProjectRoot
    Write-Ok "백엔드 창을 띄웠습니다"
}

Write-Info "백엔드가 응답할 때까지 기다리는 중..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$apiPort/health" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if ($ready) {
    if ($hasSwagger) { Write-Ok "백엔드 준비 완료  →  http://localhost:$apiPort/docs" }
    else             { Write-Ok "백엔드 준비 완료  →  http://localhost:$apiPort" }
}
else { Write-Warn2 "백엔드 응답을 확인하지 못했습니다. 백엔드 창의 오류 메시지를 확인하세요." }

# -------------------------------------------------------------
Write-Step "3/3  프론트엔드 시작 (포트 $webPort)"
# -------------------------------------------------------------
$webDir = Join-Path $ProjectRoot 'apps\web'
$hasWeb = (Test-Path (Join-Path $webDir 'node_modules'))
if (-not $hasWeb) {
    Write-Warn2 "Next.js 패키지가 설치되어 있지 않습니다 - 건너뜁니다"
    Write-Info "괜찮습니다. 픽셀 사무실은 백엔드가 직접 서빙하므로 그대로 볼 수 있습니다."
    Write-Host ""
    Write-Host "=============================================================" -ForegroundColor White
    Write-Host "  실행 완료!" -ForegroundColor Green
    Write-Host "=============================================================" -ForegroundColor White
    Write-Host ""
    Write-Host "   픽셀 사무실 :  http://localhost:$apiPort" -ForegroundColor Cyan
    Write-Host "   끄실 때는   :  .\stop.ps1" -ForegroundColor White
    Write-Host ""
    if (-not $NoBrowser -and $ready) { Start-Process "http://localhost:$apiPort" }
    exit 0
}
if (-not (Test-PortFree ([int]$webPort))) {
    Write-Warn2 "포트 $webPort 이 이미 사용 중입니다. 이미 떠 있는 것일 수 있습니다."
} else {
    $npmCmd = if (Test-Cmd 'npm.cmd') { 'npm.cmd' } else { 'npm' }
    $webCmd = "& '$npmCmd' run dev -- --port $webPort"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoExit', '-Command', $webCmd `
        -WorkingDirectory $webDir
    Write-Ok "프론트엔드 창을 띄웠습니다"
}

Write-Info "프론트엔드가 준비될 때까지 기다리는 중... (처음이면 30초 정도)"
$webReady = $false
for ($i = 0; $i -lt 80; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$webPort" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $webReady = $true; break }
    } catch { }
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
if ($webReady) {
    Write-Host "  실행 완료!" -ForegroundColor Green
} else {
    Write-Host "  실행됨 (프론트엔드 확인 필요)" -ForegroundColor Yellow
}
Write-Host "=============================================================" -ForegroundColor White
Write-Host ""
Write-Host "   픽셀 사무실 :  http://localhost:$webPort" -ForegroundColor Cyan
if ($hasSwagger) {
    Write-Host "   API 문서    :  http://localhost:$apiPort/docs" -ForegroundColor Cyan
} else {
    Write-Host "   백엔드      :  http://localhost:$apiPort" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "   끄실 때는 :  .\stop.ps1" -ForegroundColor White
Write-Host ""

if (-not $NoBrowser -and $webReady) {
    Start-Process "http://localhost:$webPort"
}
