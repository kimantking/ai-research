@echo off
REM =============================================================
REM  AI STOCK RESEARCH OFFICE - SETUP
REM
REM  Double-click launcher. Bypasses the PowerShell ExecutionPolicy
REM  for THIS PROCESS ONLY - no system setting is changed.
REM =============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
echo.
echo  ------------------------------------------------------------
echo   Press any key to close this window.
echo  ------------------------------------------------------------
pause > nul
