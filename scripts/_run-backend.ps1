<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  백엔드 실행기 (내부용)
=============================================================
 start.ps1 이 새 창에서 이 파일을 부릅니다.

 ★ 왜 별도 파일인가

   예전에는 start.ps1 이 긴 명령 문자열을 만들어
   Start-Process -Command 로 넘겼습니다. 그 문자열에 따옴표·세미콜론·
   괄호·한글이 섞이면서 창으로 전달되는 도중 깨졌고,
   백엔드가 아예 뜨지 않았습니다.

   파일로 분리하면 그런 인용부호 문제가 원천적으로 사라집니다.
   Start-Process 는 -File 과 단순한 인자만 넘기면 됩니다.
=============================================================
#>
param(
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][int]$Port,
    [ValidateSet('fastapi','standalone')][string]$Mode = 'fastapi'
)

$ErrorActionPreference = 'Continue'

# Windows 콘솔이 ANSI 색 코드를 해석하지 못해 '[32mINFO[0m' 이
# 글자 그대로 보이는 것을 막습니다.
$env:NO_COLOR = '1'
$env:PYTHONPATH = $ProjectPath
$env:PYTHONIOENCODING = 'utf-8'

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

Write-Host ""
Write-Host "=============================================================" -ForegroundColor DarkGray
Write-Host "  AI STOCK RESEARCH OFFICE  -  백엔드" -ForegroundColor White
Write-Host "  이 창을 닫지 마세요. 닫으면 시스템이 멈춥니다." -ForegroundColor White
Write-Host "" 
Write-Host "  브라우저 주소 :  http://localhost:$Port" -ForegroundColor Cyan
Write-Host "  끄실 때는     :  다른 창에서  .\stop.bat" -ForegroundColor DarkGray
Write-Host "  실행 모드     :  $Mode" -ForegroundColor DarkGray
Write-Host "=============================================================" -ForegroundColor DarkGray
Write-Host ""

Set-Location $ProjectPath

if ($Mode -eq 'fastapi') {
    # --no-access-log 만 끕니다. 로그 레벨을 올리면 우리 로거까지
    # 조용해져서 창이 텅 비어 보입니다(살아 있는지 알 수 없음).
    & $PythonExe -m uvicorn services.api.main:app `
        --host 127.0.0.1 --port $Port --no-access-log
} else {
    & $PythonExe -m services.api.standalone --port $Port
}

# 실행 파일 자체를 못 찾으면 $LASTEXITCODE 가 비어 있습니다.
$code = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { '알 수 없음' }
Write-Host ""
Write-Host "=============================================================" -ForegroundColor Red
Write-Host "  백엔드가 종료되었습니다 (exit $code)" -ForegroundColor Red
Write-Host "=============================================================" -ForegroundColor Red
Write-Host ""
Write-Host "  위에 오류 메시지가 있다면 그대로 복사해 주세요." -ForegroundColor White
Write-Host "  이 창은 자동으로 닫히지 않습니다." -ForegroundColor DarkGray
Write-Host ""
