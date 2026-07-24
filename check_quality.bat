@echo off
chcp 65001 >nul
python tools\quality_check.py
if %errorlevel% neq 0 (
    echo.
    echo [ОШИБКА] Quality gate не пройден. Перед сборкой нужно исправить найденное.
    exit /b 1
)
echo.
echo Quality gate пройден. Можно собирать приложение.
