# PowerShell script to create a desktop shortcut for Reddit Moderator Bot
# Run this script as Administrator to create the shortcut

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Reddit Moderator Bot.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\launch_bot.bat"
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Reddit Moderator Bot"
$Shortcut.IconLocation = "shell32.dll,21"  # Robot/automation icon
$Shortcut.Save()

Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "You can now launch the Reddit Moderator Bot from your desktop." -ForegroundColor Cyan
pause
