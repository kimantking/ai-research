# =============================================================
#  공통 함수 모음 (다른 스크립트들이 불러다 씁니다)
# =============================================================

$Global:ProjectRoot = Split-Path -Parent $PSScriptRoot
$Global:ComposeProject = 'ai-stock-research-office'

function Write-Step([string]$msg)  { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)    { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg) { Write-Host "  [주의] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)   { Write-Host "  [오류] $msg" -ForegroundColor Red }
function Write-Info([string]$msg)  { Write-Host "  $msg" -ForegroundColor Gray }

function Test-Cmd([string]$name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ★ 삭제 안전장치
#   프로젝트 폴더 밖의 경로는 어떤 이유로도 지우지 않습니다.
#   다른 프로젝트를 건드리는 사고는 대부분 경로 조립 실수에서 나옵니다.
function Assert-InsideProject([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    $rootFull = [System.IO.Path]::GetFullPath($Global:ProjectRoot)
    if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "안전장치 발동: '$full' 은 프로젝트 폴더($rootFull) 밖입니다. 작업을 중단합니다."
    }
    if ($full.TrimEnd('\','/') -eq $rootFull.TrimEnd('\','/')) {
        throw "안전장치 발동: 프로젝트 루트 자체를 삭제하려 했습니다."
    }
    return $true
}

function Remove-ProjectPath([string]$Path) {
    if (-not (Test-Path $Path)) { return $false }
    Assert-InsideProject $Path | Out-Null
    Remove-Item -Recurse -Force $Path
    return $true
}

function Test-PortFree([int]$Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return (-not $c)
}

function Get-PortOwner([int]$Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) { return $null }
    $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($p) { return $p.ProcessName } else { return 'unknown' }
}

# 사용 중이면 다음 빈 포트를 찾아준다. 다른 프로젝트를 절대 종료시키지 않는다.
function Find-FreePort([int]$Preferred, [int]$MaxTries = 20) {
    for ($i = 0; $i -lt $MaxTries; $i++) {
        $p = $Preferred + $i
        if (Test-PortFree $p) { return $p }
    }
    return $null
}

# .env 파일을 읽어 해시테이블로 반환
function Read-EnvFile([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content $Path) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $k = $t.Substring(0, $idx).Trim()
        $v = $t.Substring($idx + 1).Trim()
        $map[$k] = $v
    }
    return $map
}

# .env 안의 특정 키 값을 바꾼다 (없으면 추가)
function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    if (-not (Test-Path $Path)) { return }
    $lines = Get-Content $Path
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $out = $out + "$Key=$Value" }
    $out | Set-Content -Path $Path -Encoding utf8
}

function Get-EnvValue([string]$Path, [string]$Key, [string]$Default) {
    $map = Read-EnvFile $Path
    if ($map.ContainsKey($Key) -and $map[$Key] -ne '') { return $map[$Key] }
    return $Default
}

function Get-VenvPython {
    return (Join-Path $Global:ProjectRoot '.venv\Scripts\python.exe')
}

function Test-VenvHealthy {
    $py = Get-VenvPython
    if (-not (Test-Path $py)) { return $false }
    & $py -c "import sys" 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Test-DockerRunning {
    if (-not (Test-Cmd 'docker')) { return $false }
    docker info 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}
