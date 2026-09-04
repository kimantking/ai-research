<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  FETCH MARKET DATA
=============================================================
 실제 시장 데이터를 시스템에 넣습니다.

 이 스크립트가 하는 일:
   1) 백엔드가 떠 있는지 확인
   2) 선택한 공급자로 시세를 받아 저장
   3) 품질 검사 결과를 보여줌 (거래일 정렬 / 분할 의심 / 결손)

 이 스크립트가 절대 하지 않는 일:
   - 유료 API 가입, 결제, API 키 입력
   - 다른 프로젝트 폴더 접근
   - 기존 데이터 삭제 (같은 날짜는 덮어쓰기만 합니다)

 사용법:
   .\fetch-data.ps1                       # data\market\*.csv 전부
   .\fetch-data.ps1 -Provider stooq -Symbols NVDA,AMD
   .\fetch-data.ps1 -Symbols NVDA -Start 2023-01-01
=============================================================
#>
param(
    [ValidateSet('csv_file','stooq','yfinance')]
    [string]$Provider = 'csv_file',
    [string]$Symbols = '',
    [string]$Start = '',
    [string]$End = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

$envPath = Join-Path $ProjectRoot '.env'
$apiPort = Get-EnvValue $envPath 'API_PORT' '8010'
$base    = "http://localhost:$apiPort"

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  실제 시장 데이터 가져오기" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# --- 1) 백엔드 확인 ---
Write-Step "1/3  백엔드 확인"
$alive = $false
try {
    $r = Invoke-WebRequest -Uri "$base/health" -TimeoutSec 3 -UseBasicParsing
    $alive = ($r.StatusCode -eq 200)
} catch { }
if (-not $alive) {
    Write-Err "백엔드가 응답하지 않습니다 ($base)"
    Write-Info "먼저 .\start.bat 또는 .\start.ps1 을 실행하세요."
    exit 1
}
Write-Ok "백엔드 연결됨"

# --- 2) CSV 안내 ---
if ($Provider -eq 'csv_file') {
    Write-Step "2/3  CSV 파일 확인"
    $dir = Join-Path $ProjectRoot 'data\market'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $files = @(Get-ChildItem -Path $dir -Filter *.csv -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) {
        Write-Warn2 "$dir 에 CSV 가 없습니다."
        Write-Host ""
        Write-Host "  넣는 방법:" -ForegroundColor White
        Write-Host "    1) 증권사나 데이터 사이트에서 일봉 CSV 를 내려받습니다" -ForegroundColor White
        Write-Host "    2) 파일 이름을 종목코드로 바꿉니다 (예: NVDA.csv)" -ForegroundColor White
        Write-Host "    3) $dir 에 넣습니다" -ForegroundColor White
        Write-Host "    4) 이 스크립트를 다시 실행합니다" -ForegroundColor White
        Write-Host ""
        Write-Info "첫 줄 예: Date,Open,High,Low,Close,Volume"
        Write-Info "한글 머리글(일자,시가,고가,저가,종가,거래량)도 인식합니다."
        Write-Host ""
        Write-Info "인터넷에서 바로 받고 싶으면:  .\fetch-data.ps1 -Provider stooq -Symbols NVDA"
        exit 0
    }
    Write-Ok "$($files.Count)개 파일 발견: $(($files | Select-Object -First 8 | ForEach-Object { $_.BaseName }) -join ', ')"
} else {
    Write-Step "2/3  공급자 확인"
    if (-not $Symbols) {
        Write-Err "$Provider 를 쓸 때는 -Symbols 가 필요합니다."
        Write-Info "예:  .\fetch-data.ps1 -Provider $Provider -Symbols NVDA,AMD"
        exit 1
    }
    if ($Provider -eq 'stooq') {
        Write-Warn2 "Stooq 는 비공식 CSV 엔드포인트입니다. API 키는 필요 없습니다."
        Write-Info "재배포·상업적 이용 전에 stooq.com 약관을 직접 확인하십시오."
    }
    if ($Provider -eq 'yfinance') {
        Write-Warn2 "yfinance 데이터는 개인 연구용입니다. 재배포는 허용되지 않습니다."
    }
    Write-Ok "대상: $Symbols"
}

# --- 3) 적재 ---
Write-Step "3/3  적재"
$payload = @{ provider = $Provider; symbols = $Symbols; start = $Start; end = $End } | ConvertTo-Json
try {
    $res = Invoke-RestMethod -Uri "$base/api/data/load" -Method Post `
             -ContentType 'application/json; charset=utf-8' `
             -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) -TimeoutSec 180
} catch {
    Write-Err "적재 요청 실패: $_"
    exit 1
}

$loaded = @($res.loaded)
$failed = @($res.failed)

foreach ($item in $loaded) {
    $q = $item.quality
    Write-Ok "$($item.symbol) - $($item.bars)봉 저장 (PIT $($item.pit_records)건)"
    if ($q) {
        if ($q.problems -and $q.problems.Count -gt 0) {
            foreach ($p in $q.problems) { Write-Warn2 "    $p" }
        } else {
            Write-Info "    품질 검사 통과 (거래일 정렬 확인됨)"
        }
    }
}
foreach ($item in $failed) {
    Write-Err "$($item.symbol) - $($item.error)"
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
if ($loaded.Count -gt 0) {
    Write-Host "  적재 완료 - $($loaded.Count)종목" -ForegroundColor Green
    Write-Host "=============================================================" -ForegroundColor White
    Write-Host ""
    Write-Host "  브라우저에서 Markets 화면을 열어 확인하세요:" -ForegroundColor White
    Write-Host "      $base/#markets" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ※ 적재한 종목만 실제 데이터입니다. 나머지는 여전히 합성입니다." -ForegroundColor DarkGray
    Write-Host "     화면 배지가 MIXED 로 바뀌는 것이 정상입니다." -ForegroundColor DarkGray
    Write-Host ""
    exit 0
} else {
    Write-Host "  적재된 종목이 없습니다" -ForegroundColor Yellow
    Write-Host "=============================================================" -ForegroundColor White
    Write-Host ""
    if ($res.error) { Write-Info $res.error }
    Write-Info "도움말: docs\MARKET_DATA.md"
    Write-Host ""
    exit 0
}
