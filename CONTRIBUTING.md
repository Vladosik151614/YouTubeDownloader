# Contributing

Thanks for considering a contribution.

## Before Opening a Pull Request

Run the local checks:

```powershell
python tools\privacy_check.py
python tools\quality_check.py
```

Do not commit:

- `build/`, `dist/`, `release/`;
- `.exe`, `.dll`, `.zip`;
- cookies or access files;
- logs;
- local settings;
- personal Windows paths;
- API keys, tokens or passwords.

## Development Notes

- Keep user-facing text non-technical.
- Put advanced diagnostics behind Developer Mode.
- Keep generated screenshots free of personal data.
- Follow `docs/ENGINEERING_STANDARDS.md` before large refactors.

## Pull Request Checklist

- The privacy check passes.
- The quality check passes.
- The app still starts locally.
- Documentation is updated when UI or behavior changes.

## Reporting Bugs

Please include:

- app version;
- Windows version;
- service/link type, for example YouTube playlist or SoundCloud track;
- what you clicked before the problem happened;
- the visible error message;
- a sanitized support report from the app, if available.

Do not include:

- cookies;
- passwords;
- tokens or API keys;
- private browser data;
- private local file paths;
- private account-only links.

If a report contains private data, it may be removed instead of debugged.
