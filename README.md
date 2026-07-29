# YouTube Downloader

[![CI](https://github.com/Vladosik151614/YouTubeDownloader/actions/workflows/ci.yml/badge.svg)](https://github.com/Vladosik151614/YouTubeDownloader/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Vladosik151614/YouTubeDownloader?label=release)](https://github.com/Vladosik151614/YouTubeDownloader/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Vladosik151614/YouTubeDownloader/total?label=downloads)](https://github.com/Vladosik151614/YouTubeDownloader/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Windows desktop downloader for video, music, playlists, channels and clips from supported public services.

Version target: `0.1.3`

![Download screen](docs/assets/screenshots/01-download-annotated.png)

## Features

- Download video and audio from supported services.
- Save YouTube, Spotify, SoundCloud, Twitch and TikTok content where supported by the download system.
- Choose quality, FPS, container and H.264 conversion profile.
- Use a separate app Chrome profile for restricted content when sign-in is required.
- Keep public downloads working without account sign-in.
- Download history, retry, open folder and queue controls.
- Built-in bug-fix report with dated release notes.
- Pause and continue downloads using the same partial files where the service supports resume.
- Local browser interface for development checks: `python main.py --web`.
- Structured proxy settings and a lightweight speed check for concurrency recommendations.
- Background tray mode, exit confirmation and completion notifications.
- Sanitized support reports that avoid cookies, tokens and local user paths.
- Local settings and history stored outside the source folder.
- Separate service folders for Spotify, SoundCloud, YouTube, Twitch and TikTok.

## Documentation

- [User Guide EN](docs/USER_GUIDE_EN.md)
- [Руководство RU](docs/USER_GUIDE_RU.md)
- [Privacy Policy](PRIVACY.md)
- [User Agreement](USER_AGREEMENT.md)
- [Changelog](CHANGELOG.md)
- [Engineering Standards](docs/ENGINEERING_STANDARDS.md)

## Default Download Profile

- Video
- 1080p
- Up to 60 FPS
- MP4
- H.264
- Automatic GPU encoder when available, CPU fallback

## Basic Usage

1. Open the app.
2. Paste a supported link.
3. Choose a download profile if needed.
4. Click `Add`.
5. Watch the queue progress.
6. Use pause, retry or cancel from the queue when needed.
7. Click the folder icon to open the saved file location.

## Run From Command Line

Version 0.1.3 is published as a Windows executable release asset.

Download and run:

```powershell
irm "https://github.com/Vladosik151614/YouTubeDownloader/releases/latest/download/YouTubeDownloaderSetup-0.1.3.exe" -OutFile "$env:TEMP\YouTubeDownloaderSetup.exe"; Start-Process "$env:TEMP\YouTubeDownloaderSetup.exe" -Wait
```

Download only:

```powershell
$url = "https://github.com/Vladosik151614/YouTubeDownloader/releases/latest/download/YouTubeDownloaderSetup-0.1.3.exe"
$installer = "$env:TEMP\YouTubeDownloaderSetup.exe"
Invoke-WebRequest $url -OutFile $installer
```

Note: a full Windows installer can be published when Inno Setup is available on the maintainer computer.

## Account Access

Sign-in is optional. Public content should download without an account.

For restricted content, open `Accounts`, choose the service and sign in once in the separate Chrome window opened by the app. The app will refresh access data automatically when needed.

The app does not use your normal Chrome profile by default.

Spotify support uses a separate music engine. Spotify tracks, albums and playlists are resolved through Spotify metadata and downloaded from available audio providers; DRM-protected Spotify audio is not decrypted.

## Privacy

The app stores settings, logs, history and access data locally on your computer. It must not include cookies, logs, settings, build folders or personal paths in the GitHub repository.

Read [PRIVACY.md](PRIVACY.md) before publishing a release.

## Reporting Problems

For release builds, the app provides a sanitized error report that can be copied or opened as a GitHub issue. Reports must not include cookies, passwords or private tokens.

## Maintainer Tools


