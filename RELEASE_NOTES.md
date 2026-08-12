# Release Notes

## 0.1.5

Release date: August 12, 2026. Release time: `2026-08-12 15:02:00 +02:00`.

TikTok profile and playlist workflow:

- Embedded the TikTok catalog directly below the controls on the first download screen; the queue remains visible and no separate catalog page opens.
- Added real cover images on selectable medium/large cards, four cards per row, per-card expandable Download actions and profile/playlist bulk actions.
- Added muted hover preview directly inside the hovered cover using TikTok's animated preview, without a permanent right-side preview panel.
- Added the actual source resolution, FPS and codec to every card, including explicit 2K and 4K labels when those sources exist.
- Applied the shared output profile to TikTok and every other video service: resolution, FPS, container, codec and encoder are snapshotted per task. The default remains 1080p/60 FPS; 2K and 4K are selectable from the main profile.
- Extended verified post-processing to container, resolution and FPS mismatches as well as codec changes; MOV and other video inputs can be converted to the selected MP4 profile.
- Added an explicit opt-in upscale switch for cases where the user wants the downloaded video processed up to the selected profile resolution. It stays disabled by default so artificial upscale is not shown as real source quality.
- Added a TikTok quality experiment report with provider, quality, FPS, codec and no-watermark verification results.
- Kept strict TikTok watermark exclusion while removing the old TikTok-only maximum-quality override that bypassed the active profile.
- Added TikTok-specific access guidance for webpage challenge failures and retained the existing cookies/account workflow.
- Updated application, installer, support report, updater and owner/public release workflow metadata to `0.1.5`.

Publication timestamp: `2026-08-12 15:02:00 +02:00` (Europe/Berlin).

## 0.1.4

Release date: August 10, 2026. Release time: `2026-08-10 22:42:39 +02:00` (Europe/Berlin).

Implemented; packaged-release verification is still pending:

- Reworked download failures into user-oriented explanations and suggested actions, including HTTP 403 responses.
- Kept the selected output folder on each queued task so changing the folder for a new link does not redirect an active video or playlist.
- Replaced the queue ETA field with the selected codec and carried the codec choice with the task.
- Applied selected codec conversion after download; source deletion is allowed only after successful conversion and when keeping originals is disabled.
- Added an on/off playlist-numbering control. It is off by default, so new files have no `001 -`, `002 -` or similar prefix unless the user enables it.
- Removed only merged yt-dlp `.m4a` format sidecars after the final video exists; standalone audio downloads are preserved.
- Widened the encoder selector so `Авто GPU` is displayed completely without clipping adjacent controls.
- Updated application, support-report, updater, installer and owner workflow version metadata to `0.1.4`.

Packaging safeguards:

- Release publishing now requires Inno Setup and stops instead of disguising a portable executable as an installer.
- GitHub Release notes are limited to this version's section.

Publication timestamp: `2026-08-10 22:42:39 +02:00` (Europe/Berlin).

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
- Public repository presentation now has current screenshots, clearer service limits, privacy-first wording and a stronger download section.

Packaging:

- The `YouTubeDownloaderSetup-0.1.3.exe` asset is built with Inno Setup 6.7.3 and supports normal and silent Windows installation.

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
