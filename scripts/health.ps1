<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  HEALTH CHECK
=============================================================
 지금 무엇이 켜져 있고 무엇이 꺼져 있는지 보여줍니다.
 아무것도 변경하지 않습니다 (읽기 전용).
=============================================================
#>
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_common.ps1')

$envPath = Join-Path $ProjectRoot '.env'
$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
$webPort = Get-EnvValue $envPath 'WEB_PORT' '3010'
$pgPort  = Get-EnvValue $envPath 'POSTGRES_PORT' '5433'
$rdPort  = Get-EnvValue $envPath 'REDIS_PORT' '6380'

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  HEALTH CHECK" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

function Show([string]$name, [bool]$ok, [string]$detail) {
    $mark  = if ($ok) { '  UP  ' } else { ' DOWN ' }
    $color = if ($ok) { 'Green' } else { 'DarkGray' }
    Write-Host ("[{0}] {1} {2}" -f $mark, $name.PadRight(22), $detail) -ForegroundColor $color
}

# --- 가상환경 ---
Show '.venv (Python)' (Test-VenvHealthy) (Get-VenvPython)

# --- .env ---
Show '.env' (Test-Path $envPath) $envPath

# --- 프론트 패키지 ---
$nm = Join-Path $ProjectRoot 'apps\web\node_modules'
Show 'node_modules' (Test-Path $nm) $nm

Write-Host ""

# --- 백엔드 ---
$apiOk = $false; $apiDetail = "http://localhost:$apiPort"
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$apiPort/health" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) {
        $apiOk = $true
        $j = $r.Content | ConvertFrom-Json
        $apiDetail = "http://localhost:$apiPort   (mock_mode=$($j.mock_mode), agents=$($j.agents_total))"
    }
} catch { }
Show 'Backend API' $apiOk $apiDetail

# --- 프론트 ---
$webOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$webPort" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $webOk = $true }
} catch { }
Show 'Frontend (Next.js)' $webOk "http://localhost:$webPort"

Write-Host ""

# --- 컨테이너 ---
if (Test-DockerRunning) {
    $names = docker ps --filter "label=com.docker.compose.project=$ComposeProject" --format '{{.Names}}'
    $pgUp = ($names -match 'airo-postgres') -ne $null -and ($names -join ' ') -match 'airo-postgres'
    $rdUp = ($names -join ' ') -match 'airo-redis'
    Show 'PostgreSQL (airo)' $pgUp "localhost:$pgPort"
    Show 'Valkey/Redis (airo)' $rdUp "localhost:$rdPort"
} else {
    Show 'Docker' $false '실행 중 아님 (지금 단계에서는 없어도 됩니다)'
}

Write-Host ""
Write-Host "-------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host " 포트 사용 현황 (다른 프로젝트 포함, 참고용)" -ForegroundColor DarkGray
foreach ($p in @($apiPort, $webPort, $pgPort, $rdPort)) {
    $owner = Get-PortOwner ([int]$p)
    if ($owner) { Write-Host ("  $p : $owner") -ForegroundColor DarkGray }
    else        { Write-Host ("  $p : (비어있음)") -ForegroundColor DarkGray }
}
Write-Host ""
