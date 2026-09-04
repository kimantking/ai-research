<#
=============================================================
 AGENT REACH 설치 (선택 사항)
=============================================================
 Agent Reach 는 AI 에이전트에게 인터넷 접근을 주는 외부 CLI 도구입니다.
   https://github.com/Panniantong/agent-reach   (MIT)

 ★ 설치하지 않아도 이 프로젝트는 100% 정상 동작합니다.
   Agent Reach 는 Phase 21(실데이터 수집)을 편하게 해주는 보조 도구입니다.

 ★ 이 스크립트가 하는 일
   - pipx 또는 프로젝트 전용 venv 로 설치 (전역 오염 없음)
   - 자격증명 불필요 채널만 기본 설치
   - 설치 후 doctor 실행

 ★ 이 스크립트가 절대 하지 않는 일
   - sudo / 관리자 권한 요구
   - --system 플래그 사용 (시스템 전역 설정 변경)
   - 쿠키 채널 자동 설정
   - 다른 프로젝트 환경 수정

 사용법:
   cd C:\ai-research
   .\scripts\install-agent-reach.ps1
   .\scripts\install-agent-reach.ps1 -Method venv     # pipx 대신 venv
   .\scripts\install-agent-reach.ps1 -Uninstall
=============================================================
#>
param(
    [ValidateSet('pipx', 'venv')]
    [string]$Method = 'pipx',
    [switch]$Uninstall,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

$VenvDir = Join-Path $ProjectRoot '.agent-reach-venv'
$PkgUrl  = 'https://github.com/Panniantong/agent-reach/archive/main.zip'

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  AGENT REACH  -  선택 설치" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# -------------------------------------------------------------
#  제거
# -------------------------------------------------------------
if ($Uninstall) {
    Write-Step "제거"
    if (Test-Cmd 'pipx') {
        pipx uninstall agent-reach 2>&1 | Out-Null
        Write-Ok "pipx 패키지 제거 시도 완료"
    }
    if (Test-Path $VenvDir) {
        Remove-ProjectPath $VenvDir | Out-Null
        Write-Ok "프로젝트 전용 venv 제거: $VenvDir"
    }
    Write-Info "자격증명은 ~\.agent-reach\ 에 남아 있을 수 있습니다."
    Write-Info "완전히 지우시려면 그 폴더를 직접 확인 후 삭제하세요."
    Write-Info "(이 스크립트는 홈 폴더를 임의로 지우지 않습니다)"
    exit 0
}

# -------------------------------------------------------------
#  경고 및 동의
# -------------------------------------------------------------
Write-Host ""
Write-Host "  설치 전에 반드시 읽어주세요" -ForegroundColor Yellow
Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  1. 이 도구는 외부 오픈소스입니다 (MIT). Anthropic 이나" -ForegroundColor Gray
Write-Host "     이 프로젝트가 만든 것이 아닙니다." -ForegroundColor Gray
Write-Host ""
Write-Host "  2. 설치 소스가 main 브랜치 zip 입니다 (버전 고정 아님)." -ForegroundColor Gray
Write-Host "     즉 설치 시점의 최신 코드를 그대로 실행합니다." -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Twitter / Instagram / LinkedIn / 샤오홍슈 등은" -ForegroundColor Gray
Write-Host "     브라우저 세션 쿠키를 저장해야 동작합니다." -ForegroundColor Gray
Write-Host "     - 대부분 플랫폼 이용약관 위반입니다" -ForegroundColor Yellow
Write-Host "     - 계정 정지 위험이 있습니다" -ForegroundColor Yellow
Write-Host "     - 이 스크립트는 그 채널을 설치하지 않습니다" -ForegroundColor Green
Write-Host ""
Write-Host "  4. 설치하지 않아도 AI STOCK RESEARCH OFFICE 는" -ForegroundColor Gray
Write-Host "     전부 정상 동작합니다." -ForegroundColor Gray
Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  설치 위치:" -ForegroundColor White
if ($Method -eq 'pipx') {
    Write-Host "    pipx 격리 환경 (전역 site-packages 오염 없음)" -ForegroundColor Gray
} else {
    Write-Host "    $VenvDir  (이 프로젝트 폴더 안)" -ForegroundColor Gray
}
Write-Host "  설치하지 않는 것: --system 플래그, 쿠키 채널, 관리자 권한" -ForegroundColor Gray
Write-Host ""

if (-not $Yes) {
    $ans = Read-Host "  진행할까요? (y/N)"
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Write-Host "  취소했습니다. 아무것도 변경되지 않았습니다." -ForegroundColor Green
        exit 0
    }
}

# -------------------------------------------------------------
#  1) 설치
# -------------------------------------------------------------
Write-Step "1/3  설치"

$exePath = $null

if ($Method -eq 'pipx') {
    if (-not (Test-Cmd 'pipx')) {
        Write-Warn2 "pipx 가 없습니다."
        Write-Info "설치하려면 (현재 사용자에게만 적용):"
        Write-Info "  py -3.12 -m pip install --user pipx"
        Write-Info "  py -3.12 -m pipx ensurepath"
        Write-Info "그 다음 PowerShell 을 새로 열고 이 스크립트를 다시 실행하세요."
        Write-Info ""
        Write-Info "또는 pipx 없이 진행:  .\scripts\install-agent-reach.ps1 -Method venv"
        exit 1
    }
    Write-Info "pipx 로 설치 중... (네트워크 상태에 따라 1~3분)"
    pipx install $PkgUrl
    if ($LASTEXITCODE -ne 0) {
        Write-Err "설치 실패. 네트워크 또는 방화벽을 확인하세요."
        Write-Info "이 프로젝트는 Agent Reach 없이도 정상 동작합니다."
        exit 1
    }
    $exePath = (Get-Command agent-reach -ErrorAction SilentlyContinue).Source
    Write-Ok "설치 완료 (pipx)"
} else {
    if (-not (Test-Cmd 'py')) {
        Write-Err "Python 런처(py)가 없습니다. .\setup.ps1 을 먼저 실행하세요."
        exit 1
    }
    if (-not (Test-Path $VenvDir)) {
        Write-Info "프로젝트 전용 venv 생성: $VenvDir"
        py -3.12 -m venv $VenvDir
    }
    $venvPy = Join-Path $VenvDir 'Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Err "venv 생성 실패"
        exit 1
    }
    Write-Info "패키지 설치 중..."
    & $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $venvPy -m pip install $PkgUrl
    if ($LASTEXITCODE -ne 0) {
        Write-Err "설치 실패."
        Write-Info "이 프로젝트는 Agent Reach 없이도 정상 동작합니다."
        exit 1
    }
    $exePath = Join-Path $VenvDir 'Scripts\agent-reach.exe'
    Write-Ok "설치 완료 (프로젝트 전용 venv)"
}

# -------------------------------------------------------------
#  2) 의존성 확인 (자격증명 불필요 채널만)
# -------------------------------------------------------------
Write-Step "2/3  기본 채널 준비 (자격증명 불필요한 것만)"

if ($exePath -and (Test-Path $exePath)) {
    Write-Info "실행 파일: $exePath"
    # ★ --system 을 붙이지 않습니다. 시스템 전역 설정을 바꾸지 않기 위해서입니다.
    & $exePath install --env=auto
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "일부 의존성 준비에 실패했습니다. doctor 결과를 확인하세요."
    } else {
        Write-Ok "기본 채널 준비 완료 (web / rss / youtube / github)"
    }
} else {
    Write-Warn2 "실행 파일을 찾지 못했습니다. PowerShell 을 새로 열고 확인해 보세요."
}

# -------------------------------------------------------------
#  3) 진단
# -------------------------------------------------------------
Write-Step "3/3  진단 (agent-reach doctor)"
if ($exePath -and (Test-Path $exePath)) {
    & $exePath doctor
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  완료" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor White
Write-Host ""
Write-Host "  우리 시스템이 자동으로 감지합니다. 확인:" -ForegroundColor White
Write-Host "      .\start.ps1   →  Data 화면" -ForegroundColor Cyan
Write-Host ""
Write-Host "  설정 파일:  config\data_sources\agent_reach.yaml" -ForegroundColor White
Write-Host "  설명 문서:  docs\AGENT_REACH.md" -ForegroundColor White
Write-Host ""
Write-Host "  ※ 쿠키가 필요한 채널(Twitter 등)은 켜지지 않았습니다." -ForegroundColor Yellow
Write-Host "     위험을 이해하신 뒤 설정 파일에서 직접 켜셔야 합니다." -ForegroundColor Yellow
Write-Host ""
Write-Host "  ※ 무엇을 가져오든 Research Firewall 을 통과해야" -ForegroundColor Gray
Write-Host "     에이전트에게 전달됩니다. 등급도 우리 규칙으로 다시 정합니다." -ForegroundColor Gray
Write-Host ""
