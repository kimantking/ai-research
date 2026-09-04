<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  STOP
=============================================================
 이 프로젝트의 백엔드/프론트엔드/컨테이너만 종료합니다.

 ★ 안전 보장
   - docker compose -p ai-stock-research-office down  (이 프로젝트만)
   - -v 옵션을 절대 붙이지 않습니다 → 데이터 볼륨은 그대로 남습니다
   - 다른 프로젝트의 컨테이너/프로세스는 건드리지 않습니다
=============================================================
#>
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_common.ps1')

$envPath = Join-Path $ProjectRoot '.env'
$apiPort = [int](Get-EnvValue $envPath 'API_PORT' '8010')
$webPort = [int](Get-EnvValue $envPath 'WEB_PORT' '3010')

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  AI STOCK RESEARCH OFFICE  -  STOP" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

function Stop-PortProcess([int]$Port, [string]$Label) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Info "$Label (포트 $Port): 실행 중이 아님"; return }
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if (-not $p) { continue }
        # 안전장치: 우리가 띄운 종류의 프로세스만 종료한다
        $allowed = @('python', 'pythonw', 'node', 'uvicorn')
        if ($allowed -notcontains $p.ProcessName.ToLower()) {
            Write-Warn2 "$Label (포트 $Port): '$($p.ProcessName)' 는 우리 프로세스가 아니어서 건드리지 않습니다"
            continue
        }
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction Stop
            Write-Ok "$Label 종료됨 (PID $($p.Id), $($p.ProcessName))"
        } catch {
            Write-Warn2 "$Label 종료 실패 (PID $($p.Id))"
        }
    }
}

Write-Step "1/2  애플리케이션 종료"
Stop-PortProcess $apiPort '백엔드 API'
Stop-PortProcess $webPort '프론트엔드'

Write-Step "2/2  컨테이너 종료"
if (Test-DockerRunning) {
    Push-Location $ProjectRoot
    try {
        # ★ -v 없음. 볼륨(데이터)은 보존됩니다.
        docker compose -p $ComposeProject down
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "이 프로젝트 컨테이너만 종료됨 (데이터는 그대로 보존)"
        } else {
            Write-Info "종료할 컨테이너가 없습니다"
        }
    } finally { Pop-Location }
} else {
    Write-Info "Docker가 실행 중이 아닙니다 (건너뜀)"
}

Write-Host ""
Write-Host "  종료 완료. 다른 프로젝트에 영향 없음." -ForegroundColor Green
Write-Host ""
