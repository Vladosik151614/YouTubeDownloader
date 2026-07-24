param(
    [string]$ExePath = "$env:USERPROFILE\Desktop\YouTubeDownloader.exe",
    [string]$IconPath = "$env:USERPROFILE\Desktop\YouTubeDownloader\youtube.ico"
)

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$links = Get-ChildItem -LiteralPath $desktop -Filter "*.lnk" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*YouTube*" -or $_.Name -like "*Downloader*" }

foreach ($link in $links) {
    $shortcut = $shell.CreateShortcut($link.FullName)
    if ($shortcut.TargetPath -eq $ExePath -or $link.BaseName -like "*YouTube*Downloader*") {
        $shortcut.TargetPath = $ExePath
        $shortcut.IconLocation = "$IconPath,0"
        $shortcut.Save()
    }
}

Write-Host "Desktop shortcuts updated:" $links.Count
