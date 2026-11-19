import os, tempfile, subprocess, shutil
from app.binary_manager import get_binary_path
from app.process_utils import hidden_subprocess_kwargs
from app.logger import logger

def remux_video_container(path, container, item_id=''):
    """Convert the container without re-encoding; never lose the staged source."""
    from app.download_artifacts import validate_video_with_audio
    container = str(container or 'mp4').lower().lstrip('.')
    if container not in {'mp4', 'mkv', 'webm'}:
        raise RuntimeError('Выбран неподдерживаемый контейнер')
    base, ext = os.path.splitext(path)
    if ext.lower() == '.' + container:
        return path
    tmp_fd, temp = tempfile.mkstemp(prefix='.ytdl-remux-', suffix='.' + container, dir=os.path.dirname(path))
    os.close(tmp_fd)
    try:
        cmd = [get_binary_path('ffmpeg'), '-y', '-v', 'error', '-i', path,
               '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', temp]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **hidden_subprocess_kwargs())
        valid, detail = validate_video_with_audio(temp) if proc.returncode == 0 else (False, '')
        if not valid:
            logger.warning('[%s] stage=remux outcome=failed source=%s target=%s error=%s',
                           item_id, ext, container, (proc.stderr or detail)[-1000:])
            raise RuntimeError(f'Не удалось сохранить доступные дорожки в {container.upper()} без перекодирования; исходный файл сохранён.')
        for number in range(1, 10001):
            output = f'{base}.{container}' if number == 1 else f'{base} ({number}).{container}'
            try:
                os.link(temp, output)
                break
            except FileExistsError:
                continue
            except OSError:
                created = False
                try:
                    try:
                        with open(output, 'xb') as target:
                            created = True
                            with open(temp, 'rb') as source:
                                shutil.copyfileobj(source, target, length=1024 * 1024)
                    except FileExistsError:
                        raise
                    except Exception:
                        if created and os.path.exists(output):
                            os.unlink(output)
                        raise
                    break
                except FileExistsError:
                    continue
        else:
            raise RuntimeError('Не удалось подобрать имя файла после обработки контейнера')
        os.unlink(path)
        logger.info('[%s] stage=remux outcome=success source=%s target=%s', item_id, ext, container)
        return output
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
