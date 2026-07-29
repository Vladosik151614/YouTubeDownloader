# Maintainer Workflow

This document defines how future work on YouTube Downloader should be handled.
It is written for the project owner and Codex as co-maintainers of the same
repository.

## Core Rule

Every product change must be handled as a full project update, not as an
isolated code edit.

When the app changes, check whether the following also need updates:

- app code and UI;
- settings and defaults;
- localization for Russian, English, German and Italian;
- in-app Fixes report;
- user guides;
- README and GitHub presentation;
- release notes and changelog;
- screenshots;
- installer and release assets;
- privacy and quality checks;
- public/owner repository sync.

## Before Starting Work

1. Check `git status --short`.
2. Read the affected files before editing.
3. Decide whether the change is:
   - client/public functionality;
   - owner-only functionality;
   - documentation or GitHub presentation;
   - release/installer work.
4. Keep owner-only features out of the public repository.

## Desktop Verification

For visual or workflow changes, Codex should ask for or take desktop control
when needed and verify the real desktop app, not only source code.

Use desktop verification when changing:

- layout, themes, icons or scaling;
- queue/history/actions;
- settings pages;
- accounts/access flow;
- installer behavior;
- screenshots or user instructions.

Screenshots must include only the application window. Do not capture the
desktop, personal files, browser accounts, private paths, cookies, tokens or
real private downloads.

## Screenshots and Instructions

When UI changes affect docs, regenerate screenshots before updating guides.

Stable screenshot paths:

- `docs/assets/screenshots/01-main-download.png`
- `docs/assets/screenshots/02-queue-history.png`
- `docs/assets/screenshots/03-quality-settings.png`
- `docs/assets/screenshots/04-accounts-profile.png`
- `docs/assets/screenshots/05-privacy-report.png`
- `docs/assets/screenshots/06-theme-preview.png`

After screenshots are updated, check:

- `README.md`;
- `docs/USER_GUIDE_EN.md`;
- `docs/USER_GUIDE_RU.md`;
- release notes if the visual change is part of a release.

## Fix Reporting

Every meaningful bug fix or feature should be reflected in the app's visible
Fixes report unless it is owner-only.

Update:

- `app/fix_report_page.py` for public/client-visible changes;
- owner-only local report only for private maintainer notes;
- `CHANGELOG.md`;
- `RELEASE_NOTES.md` when preparing or updating a release.

Do not add owner-only systems to the public Fixes report.

## Localization

User-facing text should support:

- Russian;
- English;
- German;
- Italian.

If new text appears in the UI, check `app/localization.py`. Russian can stay as
source text, but selected languages must display their own labels where
reasonable.

## GitHub and Public Presentation

When repository presentation changes, check:

- GitHub description;
- GitHub topics;
- README top section;
- screenshots;
- download links;
- supported services and limitations;
- privacy/safety wording;
- issue templates;
- contributing guidance.

The public repository should quickly answer:

- what the app is;
- why it is different;
- whether it is safe;
- how to install it;
- what services are supported;
- what the current UI looks like.

## Release Workflow

Use the owner workflow for release work.

Before release:

1. Update app version constants.
2. Update installer version.
3. Update `README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`.
4. Update in-app Fixes report.
5. Regenerate screenshots if UI changed.
6. Run checks.

Required checks:

```powershell
python tools\privacy_check.py
python tools\quality_check.py
```

Release publishing should go through the app owner workflow or the same worker
used by the owner panel, so the behavior matches the in-app button.

## Source Sync Without Release

Use source sync when files should be updated on GitHub but no new installer
release is needed.

Source sync should:

- push full owner source to the private owner repository;
- push sanitized public source to the public repository;
- keep owner-only files out of public;
- not create a new GitHub Release.

Do not tell users they received an app update from source sync alone. Normal
users need a new release asset/installer for application updates.

## Privacy and Safety

Never commit or publish:

- cookies;
- tokens;
- passwords;
- private browser data;
- local settings;
- logs with private data;
- personal Windows paths;
- `build/`, `dist/`, `release/`, `__pycache__/`.

Run privacy checks before every sync or release.

## Final Validation

Before saying the work is complete, verify:

- app starts if app behavior changed;
- desktop UI was checked if visual behavior changed;
- docs and screenshots match the current UI;
- all local Markdown links work;
- privacy and quality checks pass;
- public repo does not contain owner-only files;
- Git status is clean after push/sync if publishing was requested.

## Collaboration Rule

The owner decides product direction. Codex should still give engineering advice
when something affects security, privacy, release quality, maintainability or
user trust.

If Codex needs desktop access, fresh screenshots, GitHub access or a new
instruction file, it should say that directly before continuing.
