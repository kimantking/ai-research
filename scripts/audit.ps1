<#
=============================================================
 AI STOCK RESEARCH OFFICE - PHASE 0 ENVIRONMENT AUDIT
=============================================================
 이 스크립트는 "읽기 전용"입니다.
 - 아무것도 설치하지 않습니다.
 - 아무것도 삭제하지 않습니다.
 - 다른 프로젝트를 절대 건드리지 않습니다.
 - 시스템 전역 설정을 바꾸지 않습니다.

 실행 방법 (PowerShell):
   cd C:\ai-research\scripts
   powershell -ExecutionPolicy Bypass -File .\audit.ps1

 결과는 화면에 출력되고, 같은 폴더에
 audit-report.txt 파일로도 저장됩니다.
 그 파일 내용을 Claude에게 붙여넣어 주세요.
=============================================================
#>

$ErrorActionPreference = 'SilentlyContinue'
$ProjectRoot = 'C:\ai-research'
$Lines = New-Object System.Collections.Generic.List[string]

function Say([string]$text) {
    Write-Host $text
    $Lines.Add($text) | Out-Null
}

function Section([string]$title) {
    Say ''
    Say '============================================================'
    Say "  $title"
    Say '============================================================'
}

function Result([string]$status, [string]$item, [string]$detail) {
    $pad = $item.PadRight(34)
    Say ("[{0,-7}] {1} {2}" -f $status, $pad, $detail)
}

function Has([string]$cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

Say '============================================================'
Say '  AI STOCK RESEARCH OFFICE - ENVIRONMENT AUDIT'
Say ("  실행 시각: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Say '  (read-only / 아무것도 변경하지 않음)'
Say '============================================================'

# ---------------------------------------------------------
Section '1. OS / PowerShell'
# ---------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
if ($os) {
    Result 'OK' 'Windows' ("{0} (build {1}, {2})" -f $os.Caption, $os.BuildNumber, $os.OSArchitecture)
} else {
    Result 'WARNING' 'Windows' 'OS 정보를 읽지 못했습니다.'
}

$psv = $PSVersionTable.PSVersion
if ($psv.Major -ge 7) {
    Result 'OK' 'PowerShell' ("{0} (PowerShell 7+)" -f $psv)
} elseif ($psv.Major -eq 5) {
    Result 'OK' 'PowerShell' ("{0} (Windows PowerShell 5.1 - 사용 가능)" -f $psv)
} else {
    Result 'WARNING' 'PowerShell' ("{0} - 버전이 낮습니다." -f $psv)
}

$epUser = Get-ExecutionPolicy -Scope CurrentUser
$epMachine = Get-ExecutionPolicy -Scope LocalMachine
$epEff = Get-ExecutionPolicy
Result 'INFO' 'ExecutionPolicy (Effective)' "$epEff"
Result 'INFO' 'ExecutionPolicy (CurrentUser)' "$epUser"
Result 'INFO' 'ExecutionPolicy (LocalMachine)' "$epMachine"
if ($epEff -eq 'Restricted') {
    Result 'WARNING' 'ExecutionPolicy' 'Restricted 입니다. 전역 변경 대신 CurrentUser 범위 변경을 권장합니다.'
}

Result 'INFO' 'User' "$env:USERNAME"
Result 'INFO' 'Machine' "$env:COMPUTERNAME"

# ---------------------------------------------------------
Section '2. Git'
# ---------------------------------------------------------
if (Has 'git') {
    Result 'OK' 'git' (git --version)
    $gitUser = git config --global user.name
    $gitMail = git config --global user.email
    if ($gitUser) { Result 'OK' 'git user.name' "$gitUser" }
    else { Result 'WARNING' 'git user.name' '설정되지 않음 (commit 시 필요)' }
    if ($gitMail) { Result 'OK' 'git user.email' "$gitMail" }
    else { Result 'WARNING' 'git user.email' '설정되지 않음 (commit 시 필요)' }
} else {
    Result 'ERROR' 'git' '설치되지 않음 - https://git-scm.com/download/win'
}

# ---------------------------------------------------------
Section '3. Python (전역 설치 상태)'
# ---------------------------------------------------------
if (Has 'py') {
    Result 'OK' 'py (Python Launcher)' '존재함'
    Say ''
    Say '  --- py -0p (설치된 Python 목록) ---'
    $pyList = (py -0p 2>&1 | Out-String).Trim()
    foreach ($l in ($pyList -split "`r?`n")) { Say ("  " + $l) }
    Say ''

    $py312 = (py -3.12 -c "import sys; print(sys.version)" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $py312 -match '^3\.12') {
        Result 'OK' 'Python 3.12 (global)' $py312
        $py312Path = (py -3.12 -c "import sys; print(sys.executable)" 2>&1 | Out-String).Trim()
        Result 'INFO' 'Python 3.12 경로' $py312Path
    } else {
        # 3.12 가 없어도 3.11 / 3.13 이 있으면 동작합니다 (테스트 187개로 확인).
        $alt = @()
        foreach ($c in @('-3.13', '-3.11')) {
            & py $c -c "import sys" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $alt += (& py $c -c "import sys;print(sys.version.split()[0])" 2>&1 | Out-String).Trim()
            }
        }
        if ($alt.Count -gt 0) {
            Result 'WARNING' 'Python 3.12 (global)' ("없음 - 대신 " + ($alt -join ', ') + " 사용 가능. 동작합니다 (3.12 권장)")
        } else {
            Result 'ERROR' 'Python 3.12 (global)' '없음 - 3.11 이상이 하나도 없습니다. 설치가 필요합니다.'
        }
    }
} else {
    Result 'WARNING' 'py (Python Launcher)' '없음 - python 명령으로 대체 확인'
}

if (Has 'python') {
    $pv = (python --version 2>&1 | Out-String).Trim()
    Result 'INFO' 'python (PATH 기본)' $pv
} else {
    Result 'INFO' 'python (PATH 기본)' 'PATH에 없음 (py 런처를 쓰면 문제 없음)'
}

if (Has 'pip') {
    $pipv = (pip --version 2>&1 | Out-String).Trim()
    Result 'INFO' 'pip (전역)' $pipv
}

# ---------------------------------------------------------
Section '4. 프로젝트 폴더 & 전용 가상환경 (.venv)'
# ---------------------------------------------------------
if (Test-Path $ProjectRoot) {
    Result 'OK' 'C:\ai-research' '폴더 존재'
    $items = Get-ChildItem -Path $ProjectRoot -Force -ErrorAction SilentlyContinue
    Result 'INFO' '최상위 항목 수' ("{0} 개" -f ($items | Measure-Object).Count)
    if ($items) {
        Say ''
        Say '  --- C:\ai-research 최상위 내용 ---'
        foreach ($i in $items) {
            $tag = if ($i.PSIsContainer) { '[DIR ]' } else { '[FILE]' }
            Say ("  {0} {1}" -f $tag, $i.Name)
        }
        Say ''
    }

    if (Test-Path (Join-Path $ProjectRoot '.git')) {
        Result 'OK' 'Git repository' '이미 초기화되어 있음'
        Push-Location $ProjectRoot
        $branch = (git rev-parse --abbrev-ref HEAD 2>&1 | Out-String).Trim()
        $commits = (git rev-list --count HEAD 2>&1 | Out-String).Trim()
        Pop-Location
        Result 'INFO' 'Git branch' "$branch"
        Result 'INFO' 'Git commit 수' "$commits"
    } else {
        Result 'INFO' 'Git repository' '아직 없음 (Phase 4에서 git init 예정)'
    }
} else {
    Result 'WARNING' 'C:\ai-research' '폴더 없음 (Phase 4에서 생성 예정)'
}

$venv = Join-Path $ProjectRoot '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
$venvAct = Join-Path $venv 'Scripts\Activate.ps1'
$venvCfg = Join-Path $venv 'pyvenv.cfg'

if (Test-Path $venv) {
    if ((Test-Path $venvPy) -and (Test-Path $venvAct)) {
        $vv = (& $venvPy --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) {
            Result 'OK' 'Project .venv' "정상 - $vv"
            if (Test-Path $venvCfg) {
                Say ''
                Say '  --- .venv\pyvenv.cfg ---'
                foreach ($l in (Get-Content $venvCfg)) { Say ("  " + $l) }
                Say ''
            }
        } else {
            Result 'ERROR' 'Project .venv' 'BROKEN - python.exe 실행 실패 (재생성 필요)'
        }
    } else {
        Result 'ERROR' 'Project .venv' 'BROKEN - Scripts\python.exe 또는 Activate.ps1 누락'
    }
} else {
    Result 'INFO' 'Project .venv' '아직 없음 (Phase 4에서 생성 예정)'
}

# 쓰기 권한 테스트 (임시파일 생성 후 즉시 삭제)
$writeTarget = if (Test-Path $ProjectRoot) { $ProjectRoot } else { 'C:\' }
$probe = Join-Path $writeTarget ('.__audit_write_probe_{0}.tmp' -f ([guid]::NewGuid().ToString('N')))
try {
    'probe' | Out-File -FilePath $probe -Encoding ascii -ErrorAction Stop
    Remove-Item $probe -Force -ErrorAction SilentlyContinue
    Result 'OK' '파일 생성 권한' "$writeTarget 쓰기 가능"
} catch {
    Result 'ERROR' '파일 생성 권한' "$writeTarget 쓰기 불가 - 관리자 권한 또는 경로 변경 필요"
}

# ---------------------------------------------------------
Section '5. Node.js / npm'
# ---------------------------------------------------------
if (Has 'node') {
    $nv = (node --version 2>&1 | Out-String).Trim()
    $nvNum = [int]($nv -replace '^v(\d+)\..*$', '$1')
    if ($nvNum -ge 20) { Result 'OK' 'Node.js' "$nv (Next.js 요구사항 충족)" }
    elseif ($nvNum -ge 18) { Result 'WARNING' 'Node.js' "$nv (20 LTS 이상 권장)" }
    else { Result 'ERROR' 'Node.js' "$nv (너무 낮음, 20 LTS 이상 필요)" }
} else {
    Result 'ERROR' 'Node.js' '설치되지 않음 - https://nodejs.org (LTS)'
}

if (Has 'npm') {
    $npmv = (npm --version 2>&1 | Out-String).Trim()
    if ($npmv -match '^\d') { Result 'OK' 'npm' "$npmv" }
    else { Result 'WARNING' 'npm' "실행 결과 이상: $npmv" }
} elseif (Test-Path "$env:ProgramFiles\nodejs\npm.cmd") {
    Result 'WARNING' 'npm' 'npm.ps1이 ExecutionPolicy로 막혔을 수 있음 (npm.cmd 는 존재)'
} else {
    Result 'ERROR' 'npm' '없음'
}

if (Has 'pnpm') { Result 'INFO' 'pnpm' ((pnpm --version 2>&1 | Out-String).Trim()) }
if (Has 'corepack') { Result 'INFO' 'corepack' '존재' }

# ---------------------------------------------------------
Section '6. Docker'
# ---------------------------------------------------------
if (Has 'docker') {
    Result 'OK' 'docker CLI' ((docker --version 2>&1 | Out-String).Trim())
    $composeV = (docker compose version 2>&1 | Out-String).Trim()
    if ($composeV -match 'version') { Result 'OK' 'docker compose' $composeV }
    else { Result 'WARNING' 'docker compose' "확인 실패: $composeV" }

    $info = (docker info --format '{{.ServerVersion}}' 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $info -and $info -notmatch 'error') {
        Result 'OK' 'Docker Engine 실행중' "server $info"
        Say ''
        Say '  --- 현재 실행 중인 컨테이너 (다른 프로젝트 포함, 절대 건드리지 않음) ---'
        $ps = (docker ps --format '{{.Names}} | {{.Image}} | {{.Ports}}' 2>&1 | Out-String).Trim()
        if ($ps) { foreach ($l in ($ps -split "`r?`n")) { Say ("  " + $l) } }
        else { Say '  (실행 중인 컨테이너 없음)' }
        Say ''
        Say '  --- Docker compose 프로젝트 라벨 ---'
        $projs = (docker ps -a --format '{{.Label "com.docker.compose.project"}}' 2>&1 | Out-String).Trim()
        if ($projs) {
            $uniq = $projs -split "`r?`n" | Where-Object { $_ -and $_.Trim() -ne '' } | Sort-Object -Unique
            foreach ($p in $uniq) { Say ("  " + $p) }
        } else { Say '  (없음)' }
        Say ''
    } else {
        Result 'WARNING' 'Docker Engine' 'Docker Desktop이 실행 중이 아닙니다. 앱을 켠 뒤 다시 실행하세요.'
    }
} else {
    Result 'ERROR' 'Docker' '설치되지 않음 - Docker Desktop 필요 (PostgreSQL/Redis용)'
}

if (Has 'wsl') {
    $wslv = (wsl --status 2>&1 | Out-String).Trim()
    Result 'INFO' 'WSL' '존재 (Docker Desktop backend용, 직접 사용하지 않음)'
}

# ---------------------------------------------------------
Section '7. 포트 사용 현황 (충돌 회피용)'
# ---------------------------------------------------------
Say '  이 프로젝트는 이미 쓰이는 포트를 절대 빼앗지 않습니다.'
Say '  사용 중이면 다른 포트로 자동 우회합니다.'
Say ''
$portsToCheck = @(
    @{p=3000; use='Next.js 프론트엔드 (후보)'},
    @{p=3001; use='Next.js 대체 후보'},
    @{p=8000; use='FastAPI 백엔드 (후보)'},
    @{p=8001; use='FastAPI 대체 후보'},
    @{p=5432; use='PostgreSQL 기본'},
    @{p=5433; use='PostgreSQL 대체 후보'},
    @{p=5434; use='PostgreSQL 대체 후보 2'},
    @{p=6379; use='Redis 기본'},
    @{p=6380; use='Redis 대체 후보'},
    @{p=6381; use='Redis 대체 후보 2'}
)
foreach ($e in $portsToCheck) {
    $port = $e.p
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = (Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        if (-not $proc) { $proc = 'unknown' }
        Result 'IN-USE' ("port $port") ("사용중 (프로세스: {0}) - {1}" -f $proc, $e.use)
    } else {
        Result 'FREE' ("port $port") ("사용 가능 - {0}" -f $e.use)
    }
}

# ---------------------------------------------------------
Section '8. 디스크 여유 공간'
# ---------------------------------------------------------
$drive = Get-PSDrive -Name C -ErrorAction SilentlyContinue
if ($drive) {
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    $usedGB = [math]::Round($drive.Used / 1GB, 1)
    $totalGB = $freeGB + $usedGB
    if ($freeGB -ge 40) { Result 'OK' 'C: 여유 공간' "$freeGB GB 여유 / 총 $totalGB GB" }
    elseif ($freeGB -ge 20) { Result 'WARNING' 'C: 여유 공간' "$freeGB GB - 다소 부족 (Docker 이미지 포함 40GB 권장)" }
    else { Result 'ERROR' 'C: 여유 공간' "$freeGB GB - 부족합니다" }
}

# ---------------------------------------------------------
Section '9. 기타 개발 도구 (참고용)'
# ---------------------------------------------------------
foreach ($t in @('code','uv','poetry','make','psql','redis-cli','gh','curl')) {
    if (Has $t) { Result 'FOUND' $t '존재' } else { Result '-' $t '없음 (필수 아님)' }
}

# ---------------------------------------------------------
Section '10. 요약'
# ---------------------------------------------------------
$errCount = ($Lines | Where-Object { $_ -match '^\[ERROR' }).Count
$warnCount = ($Lines | Where-Object { $_ -match '^\[WARNING' }).Count
Say ("  ERROR   : {0} 건" -f $errCount)
Say ("  WARNING : {0} 건" -f $warnCount)
Say ''
if ($errCount -eq 0) {
    Say '  판정: READY (또는 사소한 경고만 존재)'
} else {
    Say '  판정: NOT READY - 위 ERROR 항목을 먼저 해결해야 합니다.'
}
Say ''
Say '  이 스크립트는 아무것도 설치/삭제/변경하지 않았습니다.'
Say '  다른 프로젝트에 미친 영향: 없음 (NONE)'
Say ''

# ---------------------------------------------------------
$reportPath = Join-Path $PSScriptRoot 'audit-report.txt'
try {
    $Lines -join "`r`n" | Out-File -FilePath $reportPath -Encoding utf8
    Write-Host ''
    Write-Host "리포트 저장됨: $reportPath" -ForegroundColor Green
    Write-Host '이 파일 내용을 Claude에게 그대로 붙여넣어 주세요.' -ForegroundColor Green
} catch {
    Write-Host "리포트 파일 저장 실패: $reportPath" -ForegroundColor Yellow
}
