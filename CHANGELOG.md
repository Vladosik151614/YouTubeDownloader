# Changelog

All notable public release changes should be documented here.

## 0.1.5 - 2026-08-14

- Embedded TikTok browsing into the first download screen without a separate page or permanent right preview panel.
- Added responsive four-column cards with real covers, per-card expandable Download actions and selected/full profile or playlist actions.
- Added muted animated hover preview directly inside each card cover.
- Added per-card verified source resolution, FPS and codec labels; direct TikTok download is capped at Full HD/60 FPS where available.
- Applied one shared resolution/FPS/container/codec/encoder profile to all video services; defaults remain 1080p/60 FPS.
- Extended verified conversion to enforce container, resolution and FPS in addition to codec, including MOV-to-MP4 profile processing.
- Added an explicit opt-in upscale switch plus 2K/4K target selector to the main profile row; it runs after download and does not replace real source-quality detection.
- Added a documented TikTok quality test table covering provider, quality, FPS, codec and watermark status.
- Kept TikTok downloads strictly filtered against standard TikTok watermarked formats.
- Added specific TikTok challenge/cookies guidance.
- Publication time: `2026-08-14 05:45:07 +02:00`.

## 0.1.4 - 2026-08-10

- Implemented clearer user-facing download errors with suggested recovery actions; packaged-release verification is pending.
- Implemented per-task output-folder snapshots so later folder changes do not redirect active downloads; packaged-release verification is pending.
- Implemented codec display in the queue and codec-aware post-download conversion; packaged-release verification is pending.
- Made successful conversion a prerequisite for deleting the source when original retention is disabled; packaged-release verification is pending.
- Added optional playlist filename numbering, disabled by default.
- Cleaned up temporary merged `.m4a` format sidecars without deleting standalone audio files.
- Fixed clipping of the selected encoder name on the main download screen.
- Updated release metadata and made Inno Setup mandatory for installer publication.
- Publication time: `2026-08-10 22:42:39 +02:00` (Europe/Berlin).

## 0.1.3 - 2026-07-29

- Fixed owner GitHub panel localization for Russian, English, German and Italian.
- Fixed owner panel button labels so they fit cleanly in the current UI.
- Rechecked the Format settings layout in the desktop app.
- Added functional Developer Mode action cards for logs, support reports, access, network, video and files.
- Published a Windows installer built with Inno Setup 6.7.3.
- Refreshed public README positioning, screenshots, privacy notes and release instructions.

## 0.1.2 - 2026-07-29

- Added Spotify support through a separate spotDL-based music engine.
- Added Spotify track, album and playlist routing as audio downloads.
- Added Spotify account card and isolated login profile.
- Added Spotify link preview detection without routing Spotify URLs through yt-dlp.
- Added separate Spotify music output folders.
- Added collapsible release groups on the in-app Fix Report page.
- Updated installer and update asset flow for `YouTubeDownloaderSetup-0.1.2.exe`.

## 0.1.1 - 2026-07-28

- Fixed missing action icons in the download queue on Windows.
- Fixed missing action icons in download history.
- Replaced fragile emoji buttons with painted Qt action icons.
- Refreshed YouTube, TikTok, Twitch and SoundCloud service icons in official brand colors.
- Fixed large playlist detection when files are saved inside playlist subfolders.
- Fixed large playlists getting stuck on the information-reading step before downloads begin.
- Added expandable playlist rows in the queue: a playlist can be opened to show individual videos, titles, statuses and per-item progress.
- Added playlist thumbnail loading from metadata when a thumbnail URL is available.
- Added video thumbnails for single queue items and expanded playlist child rows when the service provides thumbnail metadata.
- Normalized all queue thumbnail images to one fixed visual size.
- Added three polished themes: Lux Graphite, Lux Midnight and Lux Silver.
- Removed old theme choices from the UI and fixed theme colors for tabs, forms, labels and panels.
- Fixed settings layout overflow that caused an unnecessary horizontal scrollbar.
- Expanded the client developer mode into Diagnostics, Logs, Network, Access, Video, Files, Experiments and Support Package tabs.
- Added client-safe developer-mode recommendations for diagnostics, access, network, codecs and support reports.
- Changed the default language to English and kept Russian, English, German and Italian in the language selector.
- Reworked runtime translations for the main screens, settings, queue, history, accounts and developer diagnostics.
- Added stylesheet caching and thumbnail caching to reduce repeated UI work.
- Changed the main action flow: Paste Link now only fills the URL field, and Download starts the queue item.
- Added a quick codec selector with Original/H.264/VP9/AV1 options.
- Added a setting to ask before codec conversion; playlist conversion asks once per playlist, single videos ask per item.
- Fixed cancellation state so cancelled downloads stay marked as cancelled instead of turning into generic errors.
- Improved expanded playlist table scrolling and redraw behavior.
- Added extra diagnostics for playlist title, target folder, format, warning count and error count.
- Improved the in-app bug-fix report with severity colors and clearer fix categories.

## 0.1.0 - 2026-07-24

- Initial public Windows release.
- Added video, audio, playlist, channel and clip download workflow.
- Added YouTube, SoundCloud, Twitch and TikTok support where supported by the download system.
- Added quality, FPS, container and H.264 conversion settings.
- Added optional account access through a separate app Chrome profile.
- Added history, queue controls, retry, folder opening and support report tools.
- Added privacy checks, quality checks and GitHub Actions CI.
- Added installer and release documentation.
