@echo off
REM Create venv (if missing), install package + deps (runtime + dev/test) editable.
setlocal

cd /d "%~dp0.."

if not exist env (
    echo Creating virtual environment in .\env ...
    python -m venv env
)

call env\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[dev]"
if errorlevel 1 exit /b 1

echo.
echo Done. Activate with:  env\Scripts\activate.bat
echo Then run:
echo   windows\run_logger.bat
echo   windows\run_analyzer.bat
echo   pytest --cov=batterylogger

