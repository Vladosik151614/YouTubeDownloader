# Authentication Architecture

The app must not depend on the user's normal Chrome profile by default.

## Current 0.1.0 Flow

- Account actions live in the desktop `Аккаунты` page.
- The app launches Chrome with an isolated `user-data-dir` under local AppData.
- The user signs in inside that isolated profile.
- The app exports cookies from that isolated profile into a Netscape cookies file under local AppData.
- Downloads automatically choose the matching cookies file by URL host.
- Manual `cookies.txt` remains as a fallback.
- `cookies-from-browser chrome` for the user's normal Chrome profile remains an emergency fallback only.

## Local Data

Runtime account data is stored under:

- `%LOCALAPPDATA%/YouTubeDownloader/auth/browser_profiles/`
- `%LOCALAPPDATA%/YouTubeDownloader/auth/cookies/`

These files must never be committed or bundled into source releases.

## Service Coverage

- YouTube: cookies help with age/account/bot-check cases.
- TikTok: cookies may help, but IP blocks still need proxy diagnostics.
- Twitch: cookies help with subscriber/private/account-limited content.
- SoundCloud: cookies help with account-limited content; some premium cases may require service-specific support.

## Future Work

- Add in-app account health checks using safe metadata requests.
- Encrypt exported cookies at rest with Windows DPAPI.
- Add proxy-per-service diagnostics for TikTok IP blocks.
- Add GitHub release updater for app binaries.
