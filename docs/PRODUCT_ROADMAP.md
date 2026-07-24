# Product Roadmap

## Implemented In 0.1.0 Track

- Download from any yt-dlp supported public URL, including YouTube, TikTok, Twitch, SoundCloud, and many other services.
- Video/audio mode.
- Quality limit: best, 2160p, 1440p, 1080p, 720p, 480p.
- FPS limit: best, 60 FPS, 30 FPS.
- Containers: MP4, MKV, WebM.
- H.264 conversion via Auto, NVIDIA NVENC, Intel QSV, AMD AMF, CPU x264.
- Playlist subfolders and playlist numbering.
- Duplicate skipping through yt-dlp download archive in local AppData.
- Optional subtitle embedding.
- Speed limit and proxy settings.
- Configurable concurrent downloads.
- Privacy and quality gates before build/publish.

## Next Product Blocks

### History

- Store local download history in AppData, not in the repo.
- Save: title, source service, output path, status, date, selected format.
- Do not store cookies, account identifiers, tokens, or private URLs in source files.

### App Updates

- Use GitHub Releases as the update source.
- App checks latest release metadata on startup when enabled.
- Stable channel ignores prereleases.
- Beta channel can show prereleases when enabled.
- Installer remains the source of application binary updates.

### Engine Updates

- Rename UI text from "yt-dlp engine" to "download system".
- Notify when a download-system update is available.
- Keep binaries in local AppData/bin.

### Browser And Authorization

- Default mode: no browser cookies and no account access.
- Advanced mode: user-provided cookies.txt for login-protected content.
- Future embedded browser must isolate profile data in AppData and must not commit profile/cache files.
- External Chrome cookie reading stays off by default because Chrome can lock or DPAPI-protect cookie databases.

### Installer

- Build with Inno Setup or NSIS.
- Include EULA and Privacy Policy acceptance step.
- Create Start Menu shortcut and optional desktop shortcut.
- Register uninstaller.
- Publish installer exe through GitHub Releases.

### Legal Texts Needed

- EULA: allowed use, no warranty, third-party tools notice.
- Privacy Policy: local-only settings/history, no analytics unless user opts in, no cookies collection by default.
- Third-party notices: yt-dlp, ffmpeg, PySide6/Qt, bundled plugin notices.
