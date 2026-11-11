@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Finalize-Git.ps1" -RepoPath "%~dp0.." -Action Menu
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Le lanceur s'est arrete avec le code %RESULT%.
pause
exit /b %RESULT%
