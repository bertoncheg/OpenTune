@echo off
set PYTHONUTF8=1
python main.py %*
if %errorlevel% neq 0 (
    echo.
    echo OpenTune crashed. See error above.
    pause
)
