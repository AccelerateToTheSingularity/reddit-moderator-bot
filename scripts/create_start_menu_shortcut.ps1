# PowerShell script to create a Start Menu shortcut for Reddit Moderator Bot
# This shortcut will launch the bot minimized to the taskbar without showing a console window

# Start Menu path for the current user
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

# Create the shortcut
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$StartMenuPath\Reddit Moderator Bot.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\..\run_hidden.vbs"
$Shortcut.WorkingDirectory = "$PSScriptRoot\.."
$Shortcut.Description = "Reddit Moderator Bot - Launches minimized to taskbar"
$Shortcut.IconLocation = "shell32.dll,21"  # Robot/automation icon
$Shortcut.Save()

Write-Host "Start Menu shortcut created successfully!" -ForegroundColor Green
Write-Host "You can now launch the Reddit Moderator Bot from the Start Menu." -ForegroundColor Cyan
Write-Host "The bot will start minimized to the taskbar without any console windows." -ForegroundColor Cyan
pause
