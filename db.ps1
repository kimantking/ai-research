<#
 루트에서 바로 실행하기 위한 얇은 래퍼입니다.
 실제 내용은 scripts\db.ps1 에 있습니다.
#>
& (Join-Path $PSScriptRoot 'scripts\db.ps1') @args
