@echo off
setlocal

cd /d "C:\Users\DELL\PycharmProjects\THRAANSH_Automation"

if not exist "logs" mkdir "logs"

REM ============================================================
REM FORCE UTF-8 FOR THRAANSH
REM Prevent crashes on ₹, Hindi, curly quotes and other Unicode
REM ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ================================================== >> "logs\scheduled_pipeline.log"
echo THRAANSH WORKER START %DATE% %TIME% >> "logs\scheduled_pipeline.log"

".venv\Scripts\python.exe" "run_pipeline\run_pipeline.py" --worker >> "logs\scheduled_pipeline.log" 2>&1

set EXITCODE=%ERRORLEVEL%

echo THRAANSH WORKER END %DATE% %TIME% EXIT=%EXITCODE% >> "logs\scheduled_pipeline.log"
echo ================================================== >> "logs\scheduled_pipeline.log"

exit /b %EXITCODE%