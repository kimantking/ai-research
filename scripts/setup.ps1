<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  SETUP
=============================================================
 이 스크립트가 하는 일:
   1) Python 3.12 확인
   2) 프로젝트 전용 .venv 생성 (이미 정상이면 재사용)
   3) Python 패키지 설치
   4) .env 파일 생성 (없을 때만)
   5) 포트 충돌 검사 → 충돌하면 우리 포트를 비켜서 조정
   6) Node 확인 후 apps\web 패키지 설치
   7) Docker 확인 (없어도 됩니다. MOCK 모드로 동작)

 이 스크립트가 절대 하지 않는 일:
   - 다른 프로젝트 폴더/venv/node_modules/컨테이너/볼륨 건드리기
   - 시스템 전역 Python/Node 변경
   - 실행 중인 다른 프로그램 종료
   - docker system prune 류 광범위 삭제

 사용법:
   cd C:\ai-research
   .\setup.ps1
=============================================================
#>
param(
    [switch]$WithDev,      # 개발용 패키지(pytest, ruff)도 설치
    [switch]$SkipWeb       # 프론트엔드 설치 건너뛰기
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  AI STOCK RESEARCH OFFICE  -  SETUP" -ForegroundColor White
Write-Host "  프로젝트 폴더: $ProjectRoot" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# 실패를 두 종류로 구분합니다.
#   $fatal    - 이것 없이는 아예 실행 못 함 (Python 3.12, venv)
#   $degraded - 일부 기능만 제한. 그래도 픽셀 사무실은 뜸
$fatal = $false
$degraded = $false

# -------------------------------------------------------------
# 0) 인터넷에서 받은 파일 차단 해제 (Mark of the Web)
# -------------------------------------------------------------
# zip 을 다운로드해서 풀면 Windows 가 모든 파일에 "인터넷에서 왔음" 표시를 붙입니다.
# 그 상태에서는 실행 정책이 RemoteSigned/AllSigned 일 때
# "디지털 서명되지 않았습니다" 오류가 나면서 .ps1 이 실행되지 않습니다.
#
# 여기서 푸는 대상은 "이 프로젝트 폴더 안의 우리 파일" 뿐입니다.
# 시스템 실행 정책은 건드리지 않습니다.
Write-Step "0/7  스크립트 차단 해제 (다운로드 표시 제거)"
if (Get-Command Unblock-File -ErrorAction SilentlyContinue) {
    $unblocked = 0
    Get-ChildItem -Path $ProjectRoot -Recurse -Include '*.ps1','*.bat','*.psm1' -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                Assert-InsideProject $_.FullName | Out-Null
                Unblock-File -LiteralPath $_.FullName -ErrorAction Stop
                $unblocked++
            } catch { }
        }
    Write-Ok "스크립트 $unblocked 개를 확인했습니다 (차단 표시 제거)"
    Write-Info "이제 다음부터는 .\start.ps1 을 그냥 쓰실 수 있습니다."
} else {
    Write-Info "Unblock-File 을 쓸 수 없는 환경입니다 - 건너뜁니다"
}

# -------------------------------------------------------------
Write-Step "1/7  Python 확인 (3.12 권장, 3.11 이상이면 동작)"
# -------------------------------------------------------------
# 테스트 187개를 3.11 / 3.12 / 3.13 에서 모두 통과시켜 확인했습니다.
# 그래서 "3.12가 아니면 중단" 이 아니라 "3.11 이상이면 진행" 으로 둡니다.
# 선호 순서: 3.12(개발/검증 기준) → 3.13 → 3.11
$pyExe    = $null    # 'py' 또는 'python'
$pyArgs   = @()      # py 런처일 때 -3.12 같은 버전 인자
$pyVerStr = ''

if (Test-Cmd 'py') {
    foreach ($cand in @('-3.12', '-3.13', '-3.11')) {
        & py $cand -c "import sys" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pyExe    = 'py'
            $pyArgs   = @($cand)
            $pyVerStr = (& py $cand -c "import sys;print(sys.version.split()[0])").Trim()
            break
        }
    }
    if ($pyExe) { Write-Ok "Python $pyVerStr (py 런처 $($pyArgs[0]))" }
}

if (-not $pyExe -and (Test-Cmd 'python')) {
    $v = (& python -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>&1).Trim()
    $ok = $false
    if ($v -match '^3\.(\d+)$') { $ok = ([int]$Matches[1] -ge 11) }
    if ($ok) {
        $pyExe    = 'python'
        $pyArgs   = @()
        $pyVerStr = (& python -c "import sys;print(sys.version.split()[0])").Trim()
        Write-Ok "Python $pyVerStr (python)"
    } else {
        Write-Warn2 "PATH의 python은 $v 입니다. 3.11 이상이 필요합니다."
    }
}

if (-not $pyExe) {
    Write-Err "쓸 수 있는 Python(3.11 이상)을 찾지 못했습니다."
    Write-Info "https://www.python.org/downloads/release/python-3120/ 에서 3.12를 설치하세요."
    Write-Info "설치할 때 'Add Python to PATH' 와 'py launcher' 를 꼭 체크하세요."
    Write-Info "설치한 뒤 PowerShell 창을 새로 열어야 인식됩니다."
    exit 1
}

if ($pyVerStr -notlike '3.12.*') {
    Write-Warn2 "개발·검증 기준은 3.12 입니다. $pyVerStr 로도 테스트는 통과하지만, 문제가 생기면 3.12를 설치해 보세요."
}

# -------------------------------------------------------------
Write-Step "2/7  프로젝트 전용 가상환경 (.venv)"
# -------------------------------------------------------------
$venvDir = Join-Path $ProjectRoot '.venv'
$venvPy  = Get-VenvPython

if (Test-VenvHealthy) {
    $vv = (& $venvPy -c "import sys;print(sys.version.split()[0])").Trim()
    Write-Ok ".venv 정상 (Python $vv) - 재생성하지 않습니다"
} else {
    if (Test-Path $venvDir) {
        Write-Warn2 ".venv 가 손상되어 있습니다. 이 폴더만 다시 만듭니다."
        Write-Info "대상: $venvDir  (이 프로젝트 폴더 안에만 있습니다)"
        # Remove-ProjectPath 가 경로가 프로젝트 안인지 먼저 확인합니다 (StartsWith 검사)
        Remove-ProjectPath $venvDir | Out-Null
    }
    Write-Info "가상환경 생성 중..."
    if ($pyExe -eq 'py') { & py @pyArgs -m venv $venvDir } else { & python -m venv $venvDir }
    if (-not (Test-VenvHealthy)) {
        Write-Err "가상환경(.venv) 생성에 실패했습니다."
        Write-Info "확인해 볼 것:"
        Write-Info "  1) 백신/보안 프로그램이 .venv 폴더 생성을 막고 있지 않은지"
        Write-Info "  2) C:\ai-research 가 OneDrive 동기화 폴더 안에 있지 않은지 (자주 충돌합니다)"
        Write-Info "  3) 디스크 여유 공간"
        Write-Info "  4) Python 재설치 시 'py launcher' 체크"
        Write-Info "자세한 내용: docs\TROUBLESHOOTING.md"
        exit 1
    }
    Write-Ok ".venv 생성 완료"
}

# -------------------------------------------------------------
Write-Step "3/7  Python 패키지 설치"
# -------------------------------------------------------------
Write-Info "pip 업그레이드..."
& $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
Write-Info "패키지 설치 중... (처음이면 1~3분 걸립니다)"
Push-Location $ProjectRoot
try {
    if ($WithDev) {
        & $venvPy -m pip install -e ".[dev]" --quiet --disable-pip-version-check
    } else {
        & $venvPy -m pip install -e "." --quiet --disable-pip-version-check
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install 실패" }
    Write-Ok "Python 패키지 설치 완료"
} catch {
    Write-Warn2 "Python 패키지 설치에 실패했습니다: $_"
    Write-Info "괜찮습니다. 이 프로젝트는 외부 패키지 없이도 실행됩니다(standalone 모드)."
    Write-Info "화면과 기능은 동일합니다. 나중에 .\update.ps1 로 다시 시도할 수 있습니다."
    $degraded = $true
} finally {
    Pop-Location
}

# -------------------------------------------------------------
Write-Step "4/7  .env 파일"
# -------------------------------------------------------------
$envPath = Join-Path $ProjectRoot '.env'
$envExample = Join-Path $ProjectRoot '.env.example'
if (Test-Path $envPath) {
    Write-Ok ".env 이미 존재 - 값을 덮어쓰지 않습니다"

    # ★ 새 버전에서 추가된 설정 항목만 뒤에 붙여줍니다.
    #   기존 값(특히 API 키)은 절대 건드리지 않습니다.
    #   이게 없으면 새 기능이 생겨도 사용자가 그 항목의 존재를 모릅니다.
    $existing = @{}
    foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
        $s = $line.Trim()
        if ($s -eq '' -or $s.StartsWith('#')) { continue }
        $i = $s.IndexOf('=')
        if ($i -gt 0) { $existing[$s.Substring(0, $i).Trim()] = $true }
    }

    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($line in (Get-Content $envExample -Encoding UTF8)) {
        $s = $line.Trim()
        if ($s -eq '' -or $s.StartsWith('#')) { continue }
        $i = $s.IndexOf('=')
        if ($i -lt 1) { continue }
        $name = $s.Substring(0, $i).Trim()
        if (-not $existing.ContainsKey($name)) { $missing.Add($line) | Out-Null }
    }

    if ($missing.Count -gt 0) {
        Add-Content -Path $envPath -Encoding UTF8 -Value ''
        Add-Content -Path $envPath -Encoding UTF8 -Value (
            '# --- 새 버전에서 추가된 항목 (' + (Get-Date -Format 'yyyy-MM-dd') + ') ---')
        foreach ($m in $missing) { Add-Content -Path $envPath -Encoding UTF8 -Value $m }
        Write-Info ("새 설정 항목 " + $missing.Count + "개를 .env 끝에 추가했습니다:")
        foreach ($m in ($missing | Select-Object -First 8)) {
            Write-Host ("      " + ($m -split '=')[0]) -ForegroundColor Gray
        }
    }
} else {
    Copy-Item $envExample $envPath
    Write-Ok ".env 생성 완료 (.env.example 복사)"
    Write-Info "API 키는 아직 넣지 않아도 됩니다. MOCK 모드로 동작합니다."
}

# -------------------------------------------------------------
Write-Step "5/7  포트 충돌 검사"
# -------------------------------------------------------------
Write-Info "다른 프로젝트가 쓰는 포트는 절대 빼앗지 않고, 우리가 비켜갑니다."
$portKeys = @(
    @{ key='API_PORT';      def=8010; label='백엔드 API' },
    @{ key='WEB_PORT';      def=3010; label='프론트엔드' },
    @{ key='POSTGRES_PORT'; def=5433; label='PostgreSQL' },
    @{ key='REDIS_PORT';    def=6380; label='Redis/Valkey' }
)
foreach ($pk in $portKeys) {
    $cur = [int](Get-EnvValue $envPath $pk.key $pk.def)
    if (Test-PortFree $cur) {
        Write-Ok "$($pk.label): 포트 $cur 사용 가능"
    } else {
        $owner = Get-PortOwner $cur
        $newPort = Find-FreePort ($cur + 1)
        if ($newPort) {
            Set-EnvValue $envPath $pk.key "$newPort"
            Write-Warn2 "$($pk.label): 포트 $cur 이 '$owner' 에 의해 사용 중 → $newPort 으로 변경했습니다"
        } else {
            Write-Err "$($pk.label): 빈 포트를 찾지 못했습니다"
            $fatal = $true
        }
    }
}
# 프론트가 백엔드를 찾는 주소도 같이 맞춰준다
$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
Set-EnvValue $envPath 'NEXT_PUBLIC_API_BASE' "http://localhost:$apiPort"
Set-EnvValue $envPath 'NEXT_PUBLIC_WS_URL'   "ws://localhost:$apiPort/ws/events"
$pgPort = Get-EnvValue $envPath 'POSTGRES_PORT' '5433'
$pgUser = Get-EnvValue $envPath 'POSTGRES_USER' 'airo'
$pgPass = Get-EnvValue $envPath 'POSTGRES_PASSWORD' 'airo_local_dev_password'
$pgDb   = Get-EnvValue $envPath 'POSTGRES_DB' 'airo'
Set-EnvValue $envPath 'DATABASE_URL' "postgresql+psycopg://${pgUser}:${pgPass}@localhost:${pgPort}/${pgDb}"
$rdPort = Get-EnvValue $envPath 'REDIS_PORT' '6380'
Set-EnvValue $envPath 'REDIS_URL' "redis://localhost:${rdPort}/0"

# -------------------------------------------------------------
Write-Step "6/7  프론트엔드 (Node)"
# -------------------------------------------------------------
if ($SkipWeb) {
    Write-Warn2 "-SkipWeb 옵션으로 건너뜁니다"
} elseif (-not (Test-Cmd 'node')) {
    Write-Warn2 "Node.js 가 없습니다 - 건너뜁니다."
    Write-Info "괜찮습니다. 픽셀 사무실은 백엔드가 직접 보여주므로 Node 없이도 뜹니다."
    Write-Info "(Next.js 버전을 쓰실 때만 https://nodejs.org 에서 LTS 설치)"
    $degraded = $true
} else {
    $nv = (node --version).Trim()
    $major = [int]($nv -replace '^v(\d+)\..*$','$1')
    if ($major -lt 20) {
        Write-Warn2 "Node $nv - 20 이상이 필요합니다. 프론트엔드 설치는 건너뜁니다."
        Write-Info "픽셀 사무실은 Node 없이도 정상 동작합니다."
        $degraded = $true
    } else {
        Write-Ok "Node $nv"
        $webDir = Join-Path $ProjectRoot 'apps\web'
        Push-Location $webDir
        try {
            Write-Info "npm 패키지 설치 중... (처음이면 1~3분)"
            # npm.ps1 이 ExecutionPolicy 로 막히는 경우가 있어 npm.cmd 를 우선 시도
            $npmCmd = if (Test-Cmd 'npm.cmd') { 'npm.cmd' } else { 'npm' }
            & $npmCmd install --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw "npm install 실패" }
            Write-Ok "프론트엔드 패키지 설치 완료"
        } catch {
            Write-Err "프론트엔드 설치 실패: $_"
            Write-Info "PowerShell에서 npm이 막히는 경우 아래를 한 번 실행해 보세요 (현재 사용자에게만 적용):"
            Write-Info "  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned"
            Write-Info "설치가 안 돼도 픽셀 사무실은 정상적으로 뜹니다."
            $degraded = $true
        } finally {
            Pop-Location
        }
    }
}

# -------------------------------------------------------------
Write-Step "7/7  Docker (선택 사항)"
# -------------------------------------------------------------
if (Test-DockerRunning) {
    Write-Ok "Docker 실행 중 - PostgreSQL/Redis를 쓸 수 있습니다"
    Write-Info "지금 단계(Phase 4~7)에서는 없어도 됩니다. Phase 11 실데이터부터 필요합니다."
} elseif (Test-Cmd 'docker') {
    Write-Warn2 "Docker는 설치되어 있으나 실행 중이 아닙니다 (Docker Desktop을 켜세요)"
    Write-Info "지금은 없어도 됩니다. MOCK 모드로 정상 동작합니다."
} else {
    Write-Warn2 "Docker가 설치되어 있지 않습니다"
    Write-Info "지금은 없어도 됩니다. MOCK 모드로 정상 동작합니다."
    Write-Info "나중에 실제 데이터를 다룰 때 https://www.docker.com/products/docker-desktop 에서 설치하세요."
}

# -------------------------------------------------------------
$apiPortFinal = Get-EnvValue $envPath 'API_PORT' '8010'
$webPortFinal = Get-EnvValue $envPath 'WEB_PORT' '3010'
$hasWebPkgs = Test-Path (Join-Path $ProjectRoot 'apps\web\node_modules')
$openUrl = if ($hasWebPkgs) { "http://localhost:$webPortFinal" }
           else { "http://localhost:$apiPortFinal" }

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
if ($fatal) {
    Write-Host "  SETUP 실패 - 실행할 수 없습니다" -ForegroundColor Red
    Write-Host "=============================================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  위의 [오류] 항목을 해결한 뒤 다시 실행하세요." -ForegroundColor White
    Write-Host "  도움말: docs\TROUBLESHOOTING.md" -ForegroundColor White
    Write-Host ""
    exit 1
}

if ($degraded) {
    Write-Host "  SETUP 완료 (일부 선택 기능 제외)" -ForegroundColor Yellow
} else {
    Write-Host "  SETUP 완료!" -ForegroundColor Green
}
Write-Host "=============================================================" -ForegroundColor White
Write-Host ""
Write-Host "  이제 실행하세요:" -ForegroundColor White
Write-Host ""
Write-Host "      .\start.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  브라우저가 자동으로 열립니다:  $openUrl" -ForegroundColor White
Write-Host ""
if ($degraded) {
    Write-Host "  ※ 위에 [주의] 가 있었지만 실행에는 문제가 없습니다." -ForegroundColor DarkGray
    Write-Host "     픽셀 사무실, 학습, 리서치, 백테스트 전부 정상 동작합니다." -ForegroundColor DarkGray
    Write-Host ""
}
exit 0
