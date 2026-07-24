@echo off
chcp 65001 >nul
echo ============================================
echo  YouTube Downloader — Установка зависимостей
echo ============================================
echo.

:: Проверяем Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден! Установите Python 3.12 с python.org
    pause
    exit /b 1
)

echo [1/4] Обновление pip...
python -m pip install --upgrade pip --quiet

echo [2/4] Установка PySide6, yt-dlp, PyInstaller...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)

echo [3/4] Создание папки bin\...
if not exist "bin" mkdir bin

echo [4/4] Скачивание yt-dlp, ffmpeg, ffprobe в папку bin\...
python -c "
import urllib.request, os, stat, zipfile, shutil, sys

bin_dir = os.path.join(os.path.dirname(os.path.abspath('.')), 'bin')
os.makedirs(bin_dir, exist_ok=True)

# yt-dlp
ytdlp_path = os.path.join('bin', 'yt-dlp.exe')
if not os.path.exists(ytdlp_path):
    print('  Скачивание yt-dlp.exe...')
    urllib.request.urlretrieve(
        'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
        ytdlp_path
    )
    print('  yt-dlp.exe — OK')
else:
    print('  yt-dlp.exe уже есть')

# ffmpeg + ffprobe (essentials build)
ffmpeg_path = os.path.join('bin', 'ffmpeg.exe')
ffprobe_path = os.path.join('bin', 'ffprobe.exe')
if not os.path.exists(ffmpeg_path) or not os.path.exists(ffprobe_path):
    print('  Скачивание ffmpeg essentials (может занять время)...')
    zip_path = os.path.join('bin', 'ffmpeg.zip')
    urllib.request.urlretrieve(
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        zip_path
    )
    print('  Распаковка ffmpeg...')
    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in z.namelist():
            if name.endswith('ffmpeg.exe') or name.endswith('ffprobe.exe'):
                basename = os.path.basename(name)
                with z.open(name) as src, open(os.path.join('bin', basename), 'wb') as dst:
                    shutil.copyfileobj(src, dst)
    os.remove(zip_path)
    print('  ffmpeg.exe + ffprobe.exe — OK')
else:
    print('  ffmpeg.exe и ffprobe.exe уже есть')
print('Готово!')
"

echo.
echo ============================================
echo  Все зависимости установлены!
echo  Запустите: python main.py
echo ============================================
pause
