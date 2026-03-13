@echo off
chcp 65001 >nul
title ProcessingReportDraft - 테스트
echo ============================================
echo   ProcessingReportDraft - 테스트 실행
echo ============================================
echo.

cd /d "%~dp0"
python -m pytest tests/ -v --tb=short 2>&1 | tee test_results.txt
echo.
echo [결과가 test_results.txt 에 저장되었습니다]
pause
