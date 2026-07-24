# Installer

Use Inno Setup to build the Windows installer.

## Build Steps

1. Run the application build so `dist/YouTubeDownloader.exe` exists.
2. Open `installer/YouTubeDownloader.iss` in Inno Setup.
3. Compile the installer.
4. The output should be placed in `release/`.

## Release Safety

Do not commit generated installer files. `release/`, `build/`, `dist/`, logs, settings and access data must stay out of the source repository.

The installer displays:

- user agreement;
- privacy information;
- install location;
- desktop shortcut option.

The uninstall section removes local app settings, logs, history and access data from AppData.
