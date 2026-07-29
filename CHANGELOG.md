# Changelog

All notable public release changes should be documented here.

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
