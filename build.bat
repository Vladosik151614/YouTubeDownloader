@echo off
chcp 65001 >nul
echo ============================================
echo  YouTube Downloader — Сборка .exe
echo ============================================
echo.

:: Проверяем pyinstaller
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] PyInstaller не найден. Запустите setup.bat сначала.
    pause
    exit /b 1
)

echo Очистка старой сборки...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo Проверка качества и приватности...
python tools\quality_check.py
if %errorlevel% neq 0 (
    echo [ОШИБКА] Проверка качества не пройдена. Сборка остановлена.
    pause
    exit /b 1
)

echo Сборка приложения...
python -m PyInstaller YouTubeDownloader.spec

if %errorlevel% neq 0 (
    echo [ОШИБКА] Сборка не удалась!
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Сборка завершена!
echo  Файл: dist\YouTubeDownloader.exe
echo ============================================
pause
