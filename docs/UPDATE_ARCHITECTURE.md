# Update Architecture

Version target: `0.1.1`

## Application Updates

The application update flow uses GitHub Releases from `Vladosik151614/YouTubeDownloader`.

Settings used by the updater:

- `github_update_repo`: repository in `owner/repo` format.
- `github_update_asset`: release asset name fragment, default `YouTubeDownloader`.
- `auto_update_app`: checks for app updates on startup.
- `auto_download_updates`: downloads the release asset after user confirmation.
- `install_beta_updates`: allows prerelease releases.

Expected GitHub release asset:

```text
YouTubeDownloader-0.1.1-portable.exe
```

Runtime flow:

1. App starts.
2. If `auto_update_app` is enabled and `github_update_repo` is configured, the app reads GitHub Releases.
3. If the latest release version is newer than the local app version, the user is prompted.
4. If the user accepts and automatic downloads are enabled, the release asset is downloaded to the Windows temp folder.
5. The app asks for confirmation, launches the downloaded build and exits.

If `github_update_repo` is empty in a local developer build, the updater is inactive and does not contact GitHub.

## Download System Updates

The developer settings page includes a separate update action for the download system. User-facing text calls this "download system" instead of exposing internal package names.

## GitHub Issue Reports

Support reports are sanitized locally. The issue button opens `https://github.com/Vladosik151614/YouTubeDownloader/issues/new` with the sanitized report body.

## Release Checklist

- Publish the repository.
- Upload `YouTubeDownloader-0.1.1-portable.exe` to GitHub Releases.
- Test update from `0.1.1` to a higher version in a separate install folder.


