@echo off
chcp 65001 >nul
python tools\privacy_check.py
if %errorlevel% neq 0 (
    echo.
    echo [ОШИБКА] Перед GitHub нужно убрать найденные данные.
    exit /b 1
)
echo.
echo Можно готовить исходники к публикации.
