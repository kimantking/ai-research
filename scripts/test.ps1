<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  TEST
=============================================================
 전체 테스트를 실행합니다. 아무것도 변경하지 않습니다.
=============================================================
#>
param([string]$Filter = '')

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot '_common.ps1')

$venvPy = Get-VenvPython
if (-not (Test-VenvHealthy)) {
    Write-Err "가상환경이 없습니다. 먼저 .\setup.ps1 을 실행하세요."
    exit 1
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  TEST" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = $ProjectRoot
    if ($Filter) {
        & $venvPy -m unittest $Filter -v
    } else {
        & $venvPy -m unittest discover -s tests -t . -v
    }
    $code = $LASTEXITCODE
} finally { Pop-Location }

Write-Host ""
if ($code -eq 0) { Write-Host "  테스트 통과" -ForegroundColor Green }
else { Write-Host "  테스트 실패" -ForegroundColor Red }
exit $code
