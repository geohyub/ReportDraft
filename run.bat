@echo off
chcp 65001 >nul
title ProcessingReportDraft - 처리보고서 초안 생성기
echo ============================================
echo   ProcessingReportDraft - 처리보고서 초안 생성기
echo   Port: 5404
echo ============================================
echo.
cd /d "%~dp0"
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [INFO] 의존성 설치 중...
    pip install -r requirements.txt
    echo.
)
echo [INFO] http://127.0.0.1:5404 에서 실행됩니다.
echo [INFO] 종료하려면 Ctrl+C 를 누르세요.
echo.
start http://127.0.0.1:5404
python main.py --port 5404
pause


if errorlevel 1 (
    echo.
    echo [Error] 앱 실행 실패 errorlevel=%errorlevel%
    echo 원인 확인 후 다시 실행해주세요.
    pause
    exit /b %errorlevel%
)
