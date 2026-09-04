<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  RESET (로컬 초기화)
=============================================================
 ★★★ 안전 설계 - 반드시 읽어주세요 ★★★

 이 스크립트는 오직 아래 것들만 지웁니다:
   - C:\ai-research\.venv
   - C:\ai-research\apps\web\node_modules
   - C:\ai-research\apps\web\.next
   - C:\ai-research\data, C:\ai-research\logs   (-IncludeData 옵션일 때만)
   - Docker: compose project "ai-stock-research-office" 의 컨테이너/볼륨만

 절대 하지 않는 것:
   - docker system prune / docker volume prune / docker container prune
   - 다른 프로젝트 폴더, .venv, node_modules 삭제
   - 다른 프로젝트 컨테이너/볼륨 삭제
   - C:\ai-research 밖의 어떤 경로도 건드리지 않음

 실행 전에 반드시 y/N 확인을 받습니다.
=============================================================
#>
param(
    [switch]$IncludeData,     # data\ 와 logs\ 도 삭제
    [switch]$IncludeVolumes,  # Docker 볼륨(DB 데이터)도 삭제
    [switch]$Yes              # 확인 프롬프트 생략 (자동화용)
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

# --- 안전장치: 프로젝트 루트가 맞는지 확인 ---
$marker = Join-Path $ProjectRoot 'pyproject.toml'
if (-not (Test-Path $marker)) {
    Write-Err "여기는 이 프로젝트의 루트가 아닌 것 같습니다: $ProjectRoot"
    Write-Err "안전을 위해 중단합니다."
    exit 1
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Yellow
Write-Host "  RESET - 이 프로젝트만 초기화합니다" -ForegroundColor Yellow
Write-Host "=============================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  프로젝트 루트: $ProjectRoot" -ForegroundColor White
Write-Host ""
Write-Host "  삭제 대상:" -ForegroundColor White

$targets = New-Object System.Collections.Generic.List[string]
$targets.Add((Join-Path $ProjectRoot '.venv'))
$targets.Add((Join-Path $ProjectRoot 'apps\web\node_modules'))
$targets.Add((Join-Path $ProjectRoot 'apps\web\.next'))
if ($IncludeData) {
    $targets.Add((Join-Path $ProjectRoot 'data'))
    $targets.Add((Join-Path $ProjectRoot 'logs'))
}

foreach ($t in $targets) {
    $exists = Test-Path $t
    $mark = if ($exists) { '삭제됨' } else { '없음 (건너뜀)' }
    Write-Host ("    - {0}   [{1}]" -f $t, $mark) -ForegroundColor Gray
}
if ($IncludeVolumes) {
    Write-Host "    - Docker 볼륨: airo_pgdata, airo_redisdata  [삭제됨]" -ForegroundColor Gray
} else {
    Write-Host "    - Docker 볼륨: 보존 (지우려면 -IncludeVolumes)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  ※ .env 파일은 지우지 않습니다 (설정 보존)" -ForegroundColor DarkGray
Write-Host "  ※ 다른 프로젝트는 절대 건드리지 않습니다" -ForegroundColor DarkGray
Write-Host ""

if (-not $Yes) {
    $ans = Read-Host "  정말 진행할까요? (y/N)"
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Write-Host "  취소했습니다. 아무것도 변경되지 않았습니다." -ForegroundColor Green
        exit 0
    }
}

# --- 1) 실행 중인 것 먼저 종료 ---
Write-Step "실행 중인 프로세스/컨테이너 종료"
& (Join-Path $PSScriptRoot 'stop.ps1')

# --- 2) 폴더 삭제 ---
Write-Step "폴더 삭제"
foreach ($t in $targets) {
    # 이중 안전장치: Remove-ProjectPath 가 StartsWith 로 프로젝트 내부인지 확인합니다
    try {
        if (Remove-ProjectPath $t) { Write-Ok "삭제: $t" }
        else { Write-Info "없음: $t" }
    } catch {
        Write-Err "$_"
        continue
    }
}

# --- 3) Docker 볼륨 (옵션) ---
if ($IncludeVolumes) {
    Write-Step "Docker 볼륨 삭제 (이 프로젝트 것만)"
    if (Test-DockerRunning) {
        Push-Location $ProjectRoot
        try {
            # ★ -p 로 이 프로젝트에만 한정. prune 계열 명령 사용 안 함.
            docker compose -p $ComposeProject down -v
            Write-Ok "airo_pgdata / airo_redisdata 삭제됨"
        } finally { Pop-Location }
    } else {
        Write-Warn2 "Docker가 실행 중이 아니어서 볼륨을 지우지 못했습니다"
    }
}

Write-Host ""
Write-Host "  RESET 완료. 다시 시작하려면:  .\setup.ps1" -ForegroundColor Green
Write-Host ""
