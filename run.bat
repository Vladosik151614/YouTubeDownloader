@echo off
chcp 65001 >nul
echo Запуск YouTube Downloader...
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ОШИБКА] Не удалось запустить. Убедитесь, что setup.bat выполнен.
    pause
)
