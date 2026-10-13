@echo off
REM Launches the analyzer (Dash web app at http://localhost:8050).
setlocal

cd /d "%~dp0.."

if not exist env\Scripts\python.exe (
    echo error: .\env not found. Run windows\run.bat first to provision it. >&2
    exit /b 1
)

env\Scripts\python.exe -m batterylogger.entrypoints.analyzer_main %*
exit /b %ERRORLEVEL%
