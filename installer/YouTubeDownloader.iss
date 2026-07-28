; Inno Setup script for YouTube Downloader 0.1.2
; Build dist\YouTubeDownloader.exe first, then compile this script with Inno Setup.

#define MyAppName "YouTube Downloader"
#define MyAppVersion "0.1.2"
#define MyAppPublisher "YouTube Downloader"
#define MyAppExeName "YouTubeDownloader.exe"

[Setup]
AppId={{7F781982-81D9-42D4-8B41-000000000100}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\YouTube Downloader
DefaultGroupName=YouTube Downloader
AllowNoIcons=yes
LicenseFile=..\USER_AGREEMENT.md
InfoBeforeFile=..\PRIVACY.md
OutputDir=..\release
OutputBaseFilename=YouTubeDownloaderSetup-0.1.2
SetupIconFile=..\youtube.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YouTube Downloader"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall YouTube Downloader"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YouTube Downloader"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,YouTube Downloader}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\YouTubeDownloader\logs"
Type: filesandordirs; Name: "{localappdata}\YouTubeDownloader\auth"
Type: filesandordirs; Name: "{localappdata}\YouTubeDownloader\bin"
Type: files; Name: "{localappdata}\YouTubeDownloader\settings.json"
Type: files; Name: "{localappdata}\YouTubeDownloader\history.json"
Type: files; Name: "{localappdata}\YouTubeDownloader\download_archive.txt"
