@echo off
REM Launches the logger (polls the BMS in cfg.ini, writes timestamped CSV rows).
setlocal

cd /d "%~dp0.."

if not exist env\Scripts\python.exe (
    echo error: .\env not found. Run windows\run.bat first to provision it. >&2
    exit /b 1
)

env\Scripts\python.exe -m batterylogger.entrypoints.logger_main %*
exit /b %ERRORLEVEL%
