<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  UPDATE
=============================================================
 의존성을 최신 상태로 맞추고 테스트를 돌립니다.

 이 프로젝트 폴더 안에서만 작업합니다.
 시스템 전역 Python/Node 를 건드리지 않습니다.

 사용법:
   .\update.ps1
   .\update.ps1 -Pull      git pull 도 함께 (원격 저장소가 있을 때)
=============================================================
#>
param([switch]$Pull, [switch]$SkipTests)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  UPDATE" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

$venvPy = Get-VenvPython
if (-not (Test-VenvHealthy)) {
    Write-Err "가상환경이 없습니다. 먼저 .\setup.ps1 을 실행하세요."
    exit 1
}

# --- 1) git pull (선택) ---
if ($Pull) {
    Write-Step "1/4  소스 업데이트"
    Push-Location $ProjectRoot
    try {
        $remote = git remote 2>&1
        if ($remote) {
            git pull --ff-only
            Write-Ok "git pull 완료"
        } else {
            Write-Info "원격 저장소가 설정되어 있지 않습니다 (건너뜀)"
        }
    } finally { Pop-Location }
} else {
    Write-Step "1/4  소스 업데이트 (건너뜀 - -Pull 옵션으로 실행 가능)"
}

# --- 2) Python 패키지 ---
Write-Step "2/4  Python 패키지"
Push-Location $ProjectRoot
try {
    & $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $venvPy -m pip install -e ".[dev]" --upgrade --quiet --disable-pip-version-check
    if ($LASTEXITCODE -eq 0) { Write-Ok "Python 패키지 최신화 완료" }
    else { Write-Warn2 "일부 패키지 설치에 실패했습니다 (standalone 모드로는 계속 동작합니다)" }
} finally { Pop-Location }

# --- 3) Node 패키지 ---
Write-Step "3/4  프론트엔드 패키지"
$webDir = Join-Path $ProjectRoot 'apps\web'
if ((Test-Cmd 'node') -and (Test-Path (Join-Path $webDir 'package.json'))) {
    Push-Location $webDir
    try {
        $npmCmd = if (Test-Cmd 'npm.cmd') { 'npm.cmd' } else { 'npm' }
        & $npmCmd install --no-audit --no-fund
        Write-Ok "프론트엔드 패키지 최신화 완료"
    } catch {
        Write-Warn2 "프론트엔드 패키지 설치 실패 (백엔드 단독 실행은 가능합니다)"
    } finally { Pop-Location }
} else {
    Write-Info "Node 가 없거나 apps\web 이 없어 건너뜁니다"
}

# --- 4) 테스트 ---
if ($SkipTests) {
    Write-Step "4/4  테스트 (건너뜀)"
} else {
    Write-Step "4/4  테스트"
    Push-Location $ProjectRoot
    try {
        $env:PYTHONPATH = $ProjectRoot
        & $venvPy -m unittest discover -s tests -t . 2>&1 | Select-Object -Last 6
        if ($LASTEXITCODE -eq 0) { Write-Ok "테스트 통과" }
        else { Write-Err "테스트 실패 - 위 출력을 확인하세요" }
    } finally { Pop-Location }
}

Write-Host ""
Write-Host "  UPDATE 완료. 실행:  .\start.ps1" -ForegroundColor Green
Write-Host ""
