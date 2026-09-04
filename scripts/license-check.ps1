<#
=============================================================
 LICENSE CHECK - 위험 라이선스 자동 탐지
=============================================================
 왜 필요한가:
   내가 직접 넣지 않은 패키지가 "간접 의존성"으로 딸려 들어오는데,
   그 중에 GPL/AGPL 이 섞이면 우리 소스를 공개해야 할 수도 있습니다.
   사람이 매번 확인할 수 없으니 스크립트로 막습니다.

 아무것도 변경하지 않습니다 (읽기 전용).
=============================================================
#>
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_common.ps1')

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  LICENSE CHECK" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

# 위험 패턴
$danger = @('AGPL', 'GPL-3', 'GPLv3', 'GPL-2', 'GPLv2', 'SSPL', 'Commons Clause', 'BUSL', 'Elastic License')
$warnOnly = @('LGPL', 'MPL')

$found = 0

# ---------------- Python ----------------
Write-Step "Python 패키지"
$venvPy = Get-VenvPython
if (Test-VenvHealthy) {
    & $venvPy -m pip show pip-licenses 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Info "pip-licenses 설치 중 (이 프로젝트 .venv 안에만)..."
        & $venvPy -m pip install pip-licenses --quiet --disable-pip-version-check
    }
    $out = & $venvPy -m piplicenses --format=csv --with-urls 2>&1
    if ($LASTEXITCODE -ne 0) {
        # 모듈명이 다른 경우 실행 파일로 시도
        $exe = Join-Path $ProjectRoot '.venv\Scripts\pip-licenses.exe'
        if (Test-Path $exe) { $out = & $exe --format=csv }
    }
    foreach ($line in $out) {
        foreach ($d in $danger) {
            if ($line -match [regex]::Escape($d)) {
                Write-Err "위험: $line"
                $found++
            }
        }
        foreach ($w in $warnOnly) {
            if ($line -match [regex]::Escape($w) -and $line -notmatch 'AGPL') {
                Write-Warn2 "확인 필요: $line"
            }
        }
    }
    if ($found -eq 0) { Write-Ok "Python 쪽 위험 라이선스 없음" }
} else {
    Write-Warn2 ".venv 가 없어서 건너뜁니다. 먼저 .\setup.ps1 을 실행하세요."
}

# ---------------- Node ----------------
Write-Step "Node 패키지"
$webDir = Join-Path $ProjectRoot 'apps\web'
if (Test-Path (Join-Path $webDir 'node_modules')) {
    Push-Location $webDir
    try {
        $npxCmd = if (Test-Cmd 'npx.cmd') { 'npx.cmd' } else { 'npx' }
        $out = & $npxCmd --yes license-checker --summary 2>&1
        $bad = 0
        foreach ($line in $out) {
            foreach ($d in $danger) {
                if ($line -match [regex]::Escape($d)) {
                    Write-Err "위험: $line"
                    $bad++; $found++
                }
            }
        }
        if ($bad -eq 0) {
            Write-Ok "Node 쪽 위험 라이선스 없음"
            Write-Info "요약:"
            $out | Select-Object -First 20 | ForEach-Object { Write-Info "  $_" }
        }
    } finally { Pop-Location }
} else {
    Write-Warn2 "node_modules 가 없어서 건너뜁니다."
}

Write-Host ""
if ($found -gt 0) {
    Write-Host "  결과: 위험 항목 $found 건 발견 - docs\LICENSE_AUDIT.md 를 확인하세요" -ForegroundColor Red
    exit 1
} else {
    Write-Host "  결과: 통과 (GPL/AGPL/SSPL/Commons Clause 없음)" -ForegroundColor Green
    exit 0
}
