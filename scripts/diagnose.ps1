<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  진단 정보 수집
=============================================================
 무슨 일이 일어나고 있는지 한 파일로 모읍니다.
 스크린샷을 여러 장 찍는 대신 이 파일 하나만 보내주시면 됩니다.

 ★ 이 스크립트가 절대 하지 않는 일
   - 아무것도 설치·삭제·변경하지 않습니다 (읽기 전용)
   - API 키·비밀번호를 파일에 쓰지 않습니다
     (.env 는 '어떤 항목이 설정돼 있는지' 만 기록합니다)
   - 프로젝트 폴더 밖을 들여다보지 않습니다

 사용법:
   .\diagnose.bat            (또는  .\scripts\diagnose.ps1)
   -> diagnostic.txt 가 만들어집니다
=============================================================
#>
param(
    [switch]$WithTests        # 테스트도 돌립니다 (1분 정도 걸립니다)
)

$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_common.ps1')

$out = Join-Path $ProjectRoot 'diagnostic.txt'
$lines = New-Object System.Collections.Generic.List[string]

function Add-Line([string]$text = '') { $lines.Add($text) | Out-Null }
function Add-Section([string]$title) {
    Add-Line ''
    Add-Line '============================================================='
    Add-Line ("  " + $title)
    Add-Line '============================================================='
}

Write-Host ""
Write-Host "진단 정보를 모으는 중..." -ForegroundColor White

Add-Line "AI STOCK RESEARCH OFFICE - 진단 정보"
Add-Line ("수집 시각: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Add-Line ("프로젝트 : " + $ProjectRoot)

# ---------------------------------------------------------------- 환경
Add-Section "1. 환경"
Add-Line ("PowerShell    : " + $PSVersionTable.PSVersion + "  (" + $PSVersionTable.PSEdition + ")")
Add-Line ("OS            : " + [System.Environment]::OSVersion.VersionString)
Add-Line ("64비트         : " + [System.Environment]::Is64BitOperatingSystem)
Add-Line ("실행 정책      : " + (Get-ExecutionPolicy))
Add-Line ("콘솔 코드페이지 : " + (chcp 2>&1))

$venvPy = Get-VenvPython
Add-Line ("가상환경 정상  : " + (Test-VenvHealthy))
Add-Line ("venv python   : " + $venvPy)
if (Test-VenvHealthy) {
    Add-Line ("venv 버전      : " + (& $venvPy -c "import sys;print(sys.version)" 2>&1))
    $fa = (& $venvPy -c "import fastapi,uvicorn;print('설치됨')" 2>&1)
    Add-Line ("FastAPI       : " + $fa)
    $yf = (& $venvPy -c "import yfinance;print('설치됨')" 2>&1 | Select-Object -First 1)
    Add-Line ("yfinance      : " + $yf)
}
if (Test-Cmd 'py') { Add-Line ("py -0p        : " + ((py -0p 2>&1 | Out-String).Trim() -replace "`r?`n", " | ")) }
Add-Line ("node          : " + (if (Test-Cmd 'node') { (node --version 2>&1) } else { '없음' }))
Add-Line ("docker 실행중  : " + (Test-DockerRunning))

# ---------------------------------------------------------------- 버전
Add-Section "2. 이 폴더의 버전"
$markers = @(
    'scripts\_run-backend.ps1',
    'fetch-data.bat',
    'packages\market_data\data_go_kr.py',
    'packages\dart\client.py',
    'packages\persistence\store.py',
    'packages\market_calendar\calendar.py',
    'docs\KOREA_DATA.md'
)
foreach ($m in $markers) {
    $p = Join-Path $ProjectRoot $m
    Add-Line ("  " + (if (Test-Path $p) { "있음  " } else { "없음  " }) + $m)
}
$ps1Count = (Get-ChildItem -Path $ProjectRoot -Filter *.ps1 -Recurse -ErrorAction SilentlyContinue |
             Where-Object { $_.FullName -notmatch '\\.venv\\' }).Count
Add-Line ("  .ps1 파일 수 : " + $ps1Count)
$docCount = (Get-ChildItem -Path (Join-Path $ProjectRoot 'docs') -Filter *.md -ErrorAction SilentlyContinue).Count
Add-Line ("  문서 수      : " + $docCount)

$gitDir = Join-Path $ProjectRoot '.git'
if (Test-Path $gitDir) {
    Push-Location $ProjectRoot
    Add-Line ("  git commit   : " + (git log -1 --format='%h %s' 2>&1))
    Pop-Location
} else {
    Add-Line "  git          : 저장소가 아닙니다 (zip 으로 받으신 상태)"
}

# ---------------------------------------------------------------- 설정
Add-Section "3. 설정 (.env) - 값은 기록하지 않습니다"
$envPath = Join-Path $ProjectRoot '.env'
if (Test-Path $envPath) {
    foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $name = $t.Substring(0, $idx).Trim()
        $val  = $t.Substring($idx + 1).Trim()
        # ★ 키·비밀번호는 절대 파일에 쓰지 않습니다. 길이만 기록합니다.
        if ($name -match 'KEY|SECRET|TOKEN|PASSWORD|PASS') {
            $shown = if ($val) { "설정됨 (" + $val.Length + "자)" } else { "비어 있음" }
        } elseif ($name -match 'DATABASE_URL|REDIS_URL') {
            $shown = if ($val) { "설정됨" } else { "비어 있음" }
        } else {
            # ★ 이메일 주소도 가립니다.
            #   이 파일을 공개 저장소에 올리시거나 남에게 보내실 수 있습니다.
            $shown = [regex]::Replace($val, '[\w.+-]+@[\w.-]+\.\w+', '<이메일 가림>')
        }
        Add-Line ("  " + $name.PadRight(24) + " = " + $shown)
    }
} else {
    Add-Line "  .env 가 없습니다. .\setup.bat 을 먼저 실행하세요."
}

# ---------------------------------------------------------------- 포트
Add-Section "4. 포트"
foreach ($key in @('API_PORT','WEB_PORT','POSTGRES_PORT','REDIS_PORT')) {
    $port = [int](Get-EnvValue $envPath $key '0')
    if ($port -le 0) { continue }
    $free = Test-PortFree $port
    $owner = if ($free) { '(비어 있음)' } else { Get-PortOwner $port }
    Add-Line ("  " + $key.PadRight(14) + " " + $port + "   " + (if ($free) { '사용 가능' } else { '사용 중' }) + "  " + $owner)
}

# ---------------------------------------------------------------- 백엔드
Add-Section "5. 백엔드 응답"
$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
$base = "http://localhost:$apiPort"
foreach ($path in @('/health', '/api/system/health', '/api/persistence', '/api/markets')) {
    try {
        $r = Invoke-WebRequest -Uri ($base + $path) -TimeoutSec 5 -UseBasicParsing
        $body = $r.Content
        if ($body.Length -gt 1200) { $body = $body.Substring(0, 1200) + " ...(생략)" }
        Add-Line ("  [200] " + $path)
        Add-Line ("        " + $body)
    } catch {
        Add-Line ("  [실패] " + $path + "  -> " + $_.Exception.Message)
    }
}

# ---------------------------------------------------------------- 데이터
Add-Section "6. 데이터"
$dbRel = Get-EnvValue $envPath 'SQLITE_PATH' 'data/airo.db'
$dbPath = Join-Path $ProjectRoot ($dbRel -replace '/', '\')
if (Test-Path $dbPath) {
    $size = (Get-Item $dbPath).Length
    Add-Line ("  저장 파일 : " + $dbPath + "  (" + [math]::Round($size/1KB) + " KB)")
} else {
    Add-Line ("  저장 파일 : 없음 (" + $dbPath + ")")
}
$mktDir = Join-Path $ProjectRoot 'data\market'
if (Test-Path $mktDir) {
    $csvs = @(Get-ChildItem -Path $mktDir -Filter *.csv -ErrorAction SilentlyContinue)
    Add-Line ("  CSV 파일  : " + $csvs.Count + "개  " +
              (($csvs | Select-Object -First 10 | ForEach-Object { $_.BaseName }) -join ', '))
    foreach ($c in ($csvs | Select-Object -First 3)) {
        $head = (Get-Content $c.FullName -TotalCount 2 -Encoding UTF8) -join ' / '
        Add-Line ("    " + $c.Name + " 첫 두 줄: " + $head)
    }
} else {
    Add-Line "  data\market 폴더가 없습니다"
}

# ---------------------------------------------------------------- 로그
Add-Section "7. 최근 로그 (마지막 40줄)"
$logDir = Join-Path $ProjectRoot 'logs'
if (Test-Path $logDir) {
    $logs = @(Get-ChildItem -Path $logDir -Filter *.log -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 2)
    if ($logs.Count -eq 0) { Add-Line "  로그 파일이 없습니다" }
    foreach ($l in $logs) {
        Add-Line ("  --- " + $l.Name + " ---")
        foreach ($ln in (Get-Content $l.FullName -Tail 40 -Encoding UTF8)) { Add-Line ("  " + $ln) }
    }
} else {
    Add-Line "  logs 폴더가 없습니다"
}

# ---------------------------------------------------------------- 테스트
if ($WithTests) {
    Add-Section "8. 테스트 결과"
    Push-Location $ProjectRoot
    try {
        $env:PYTHONPATH = $ProjectRoot
        $result = (& $venvPy -m unittest discover -s tests -t . 2>&1 | Out-String)
        $tail = ($result -split "`r?`n" | Select-Object -Last 25) -join "`r`n"
        Add-Line $tail
    } finally { Pop-Location }
} else {
    Add-Section "8. 테스트"
    Add-Line "  건너뜀. 포함하려면:  .\scripts\diagnose.ps1 -WithTests"
}

Add-Line ''
Add-Line '============================================================='
Add-Line '  끝. 이 파일에는 API 키·비밀번호가 들어 있지 않습니다.'
Add-Line '============================================================='

Assert-InsideProject $out | Out-Null
$lines -join "`r`n" | Set-Content -Path $out -Encoding UTF8

Write-Host ""
Write-Ok ("만들었습니다: " + $out)
Write-Host ""
Write-Host "  이 파일 하나만 보내주시면 됩니다." -ForegroundColor White
Write-Host "  API 키·비밀번호는 들어 있지 않습니다 (설정 여부와 길이만)." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  메모장으로 열어보시려면:" -ForegroundColor DarkGray
Write-Host "      notepad diagnostic.txt" -ForegroundColor Cyan
Write-Host ""
