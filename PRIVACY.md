# Privacy Policy

This app is designed to keep user data local.

## Local Data

The app may store the following data on the user's computer:

- settings;
- download history;
- logs;
- service access data for optional account sign-in;
- download archive used to skip duplicates.

## Account Access

Account sign-in is optional. The app uses a separate Chrome profile for supported services and does not read the user's normal Chrome profile by default.

Access data must be stored locally and must never be committed to the source repository or bundled into releases.

## Error Reports

Error reports should be sanitized before sharing. Reports must not include:

- cookies;
- passwords;
- tokens;
- full private local paths;
- proxy passwords;
- private links unless the user explicitly includes them.

## Uninstall

The installer should remove application files. Local app data should be removable during uninstall or through an in-app reset/clear data action.

## Analytics

Download statistics are disabled by default. No analytics backend is enabled for version `0.1.0`.
