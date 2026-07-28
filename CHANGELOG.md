# Changelog

All notable public release changes should be documented here.

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
- Changed the default language to English and limited the language selector to English, German and Italian.
- Reworked runtime translations for the main screens, settings, queue, history, accounts and developer diagnostics.
- Added stylesheet caching and thumbnail caching to reduce repeated UI work.
- Added owner-only fix report editor for writing maintainer notes that appear in the in-app Fixes page on the owner build.
- Added owner-only public publishing workflow that exports a sanitized copy without owner tools before pushing to the public repository.
- Added owner-only diagnostics for recent logs, error summaries, privacy/quality checks and TXT report export.
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
