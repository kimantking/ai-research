<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  LOGS
=============================================================
 이 프로젝트의 로그만 봅니다. 읽기 전용입니다.

 사용법:
   .\logs.ps1              최근 로그 100줄
   .\logs.ps1 -Follow      실시간으로 따라가기 (Ctrl+C 로 중단)
   .\logs.ps1 -Lines 500   최근 500줄
   .\logs.ps1 -Docker      컨테이너 로그
=============================================================
#>
param(
    [int]$Lines = 100,
    [switch]$Follow,
    [switch]$Docker
)

$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_common.ps1')

if ($Docker) {
    if (-not (Test-DockerRunning)) {
        Write-Warn2 "Docker 가 실행 중이 아닙니다."
        exit 0
    }
    Push-Location $ProjectRoot
    try {
        if ($Follow) {
            docker compose -p $ComposeProject logs -f --tail $Lines
        } else {
            docker compose -p $ComposeProject logs --tail $Lines
        }
    } finally { Pop-Location }
    exit 0
}

$logDir = Join-Path $ProjectRoot 'logs'
if (-not (Test-Path $logDir)) {
    Write-Warn2 "logs 폴더가 아직 없습니다."
    Write-Info "백엔드는 기본적으로 실행 창에 직접 로그를 출력합니다."
    Write-Info "파일 로그를 보려면 백엔드를 띄운 PowerShell 창을 확인하세요."
    exit 0
}

$files = Get-ChildItem -Path $logDir -Filter '*.log' -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending

if (-not $files) {
    Write-Warn2 "logs 폴더에 로그 파일이 없습니다."
    Write-Info "백엔드 실행 창의 출력을 확인하세요."
    exit 0
}

$target = $files[0].FullName
Write-Step "로그 파일: $target"

if ($Follow) {
    Get-Content -Path $target -Tail $Lines -Wait
} else {
    Get-Content -Path $target -Tail $Lines
}
