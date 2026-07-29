# Release Notes

## 0.1.3

Bug-fix release for July 29, 2026.

Fixed:

- Owner GitHub panel now follows the selected app language instead of leaving action buttons in English.
- Russian, English, German and Italian labels were added for owner-only controls.
- Format settings layout was rechecked in the desktop EXE: quality, FPS, container, codec, mode, encoder and Spotify fields no longer overlap.
- Developer mode tabs now show functional action cards instead of plain text-only descriptions.
- Release workflow now prepares public and owner assets before publishing GitHub Releases.

Updated:

- README install command and version text now point to `0.1.3`.
- In-app Fix Report now includes the `0.1.3` changes as the latest expandable group.
- GitHub release notes describe the localization and developer tooling fixes.

Packaging note:

- Inno Setup was not available on the maintainer computer during this build, so the release asset is the PyInstaller Windows executable published under the existing setup filename. A full wizard installer can be republished after Inno Setup is installed.

## 0.1.2

Feature release for July 29, 2026.

Added:

- Spotify support through a separate spotDL-based music engine.
- Spotify tracks, albums and playlists routed as audio downloads.
- Spotify account card with isolated Chrome login profile.
- Spotify link preview detection without sending Spotify URLs to yt-dlp.
- Separate Spotify music folder routing.
- Service-folder routing for YouTube, Spotify, SoundCloud, Twitch and TikTok.
- Collapsible in-app Fix Report groups by release version.
- GitHub release asset flow for `YouTubeDownloaderSetup-0.1.2.exe`.

Notes:

- Spotify support uses Spotify metadata and downloads matched audio from available providers.
- DRM-protected Spotify audio is not decrypted.
- Account sign-in remains optional.

## 0.1.1

Bug-fix release for July 28, 2026.

Fixed:

- Empty/missing queue action buttons on Windows.
- Empty/missing history action buttons.
- Unclear service icons on the Accounts page.
- Large playlist completion detection when playlist subfolders are enabled.
- Large playlist startup getting stuck before the first download begins.
- Paste Link starting work too early.
- Cancelled downloads sometimes looking like active or failed items.
- Expanded playlist table scrolling/redraw issues.
- Weak playlist logging.
- Uneven thumbnail sizing in queue rows.
- Broken theme contrast on settings pages.
- Settings layout overflow and unnecessary horizontal scrollbar.
- Incomplete and low-quality runtime translations.

Added:

- Expandable playlist rows in the download queue.
- Individual playlist video titles, statuses and progress rows.
- Playlist thumbnail loading from available metadata.
- Video thumbnails for single downloads and expanded playlist rows.
- Three themes: Lux Graphite, Lux Midnight and Lux Silver.
- Developer mode tabs: Diagnostics, Logs, Network, Access, Video, Files, Experiments and Support Package.
- Developer-mode recommendations for safe client diagnostics.
- English as the default language with improved German and Italian localization.
- Theme stylesheet cache and queue thumbnail cache for smoother UI updates.
- Quick codec selector on the main screen.
- Optional prompt before codec conversion.
- In-app bug-fix report page with severity colors.
- More detailed playlist diagnostics.
