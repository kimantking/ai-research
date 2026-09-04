<#
=============================================================
 AI STOCK RESEARCH OFFICE  -  RESTART
=============================================================
 stop.ps1 로 이 프로젝트만 끄고, start.ps1 로 다시 켭니다.
 다른 프로젝트는 건드리지 않습니다.
=============================================================
#>
param([switch]$NoBrowser, [switch]$NoDocker)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

Write-Host ""
Write-Host "=============================================================" -ForegroundColor White
Write-Host "  RESTART" -ForegroundColor White
Write-Host "=============================================================" -ForegroundColor White

& (Join-Path $PSScriptRoot 'stop.ps1')
Start-Sleep -Seconds 2

$args2 = @()
if ($NoBrowser) { $args2 += '-NoBrowser' }
if ($NoDocker)  { $args2 += '-NoDocker' }
& (Join-Path $PSScriptRoot 'start.ps1') @args2
