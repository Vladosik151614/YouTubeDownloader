# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata
import os
import ssl

datas = [('youtube.ico', '.'), ('app/assets/service_icons', 'app/assets/service_icons')]
# Some Python distributions ship a local rejected-CA list referenced by ssl.py.
# Include it only when this interpreter actually provides the file; without it
# SSLContext construction fails in a frozen application built from that runtime.
rejected_cas = os.path.join(os.path.dirname(ssl.__file__), 'codex-rejected-cas.pem')
if os.path.isfile(rejected_cas):
    datas.append((rejected_cas, '.'))
binaries = []
hiddenimports = ['yt_dlp', 'yt_dlp.extractor', 'yt_dlp.extractor.lazy_extractors', 'PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets']
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# The YouTube challenge solver is a separate package; include its scripts and
# distribution metadata in frozen builds, otherwise format discovery degrades.
tmp_ret = collect_all('yt_dlp_ejs')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
datas += copy_metadata('yt-dlp-ejs')
tmp_ret = collect_all('spotdl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pykakasi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
try:
    tmp_ret = collect_all('yt_dlp_plugins')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
except Exception:
    pass


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt links to the Windows ICU/UCRT libraries.  A developer PATH can contain
# incompatible DLLs with the same names (for example Poppler's versioned ICU).
# Keep those root-level system DLL names out of the bundle so Windows loads its
# own matching libraries instead of a different application's private copy.
if __import__('sys').platform == 'win32':
    system_dlls = {'icuuc.dll', 'icuin.dll', 'icudt.dll', 'ucrtbase.dll'}
    a.binaries = [entry for entry in a.binaries if entry[0].lower() not in system_dlls]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='YouTubeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['youtube.ico'],
)
