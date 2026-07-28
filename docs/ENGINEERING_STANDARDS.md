# Engineering Standards

These rules are the local refactoring guardrails for the project. They are meant to keep future updates safe before GitHub publishing and before building installer releases.

## Version

- Public app version is `0.1.1` for the current release track.
- Version text must be changed in one intentional versioning pass, not during unrelated UI fixes.

## File Size Limits

- Normal Python module hard limit: `450` lines.
- UI page/widget module hard limit: `550` lines.
- Temporary legacy exception: `app/main_window.py` hard limit is `900` lines; current target is to keep it below `700` lines until the next split.
- Target size for `app/main_window.py`: below `450` lines after splitting into smaller widgets.
- Python file hard size limit: `45 KB`.
- If a file crosses the hard limit, new work should split code instead of adding more logic to that file.

## Refactoring Rules

- Keep downloading logic in `app/downloader.py`.
- Keep conversion/ffmpeg logic in `app/converter.py`.
- Keep settings persistence in `app/settings_manager.py`.
- Keep settings UI in `app/settings_page.py`.
- Keep queue/table UI in `app/queue_widget.py`.
- Keep theme/QSS code in `app/theme.py`.
- Keep tray and notification integration in `app/tray_controller.py`.
- Keep network proxy normalization in `app/proxy_config.py`.
- Avoid moving unrelated code during bug fixes.
- No copied code, assets, icons, QML, or text from commercial reference apps.

## Build Safety

- Never commit `build/`, `dist/`, `__pycache__/`, logs, cookies, `.env`, or generated executables.
- Run `python tools\privacy_check.py` before sharing or pushing.
- Run `python tools\quality_check.py` before rebuilding a release.
- Build artifacts may exist temporarily, but must be removed from the project folder after copying the final exe.

## Test Expectations

- Every downloader change needs at least one public YouTube smoke test.
- Every conversion change needs CPU x264 smoke test.
- GPU encoder changes should test the selected GPU encoder when available.
- UI changes must be checked at the minimum window size.
