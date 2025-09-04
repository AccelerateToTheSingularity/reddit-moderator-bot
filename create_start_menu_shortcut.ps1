<#
Creates a Start Menu shortcut for Reddit Moderator Bot and attempts to pin it to Start.
Usage:
  Right-click > Run with PowerShell
  or from a shell: pwsh -NoProfile -ExecutionPolicy Bypass -File .\create_start_menu_shortcut.ps1

Parameters:
  -NoPin   : Create shortcuts but skip pinning
  -Hidden  : Shortcut runs without console window (uses run_hidden.vbs)

Note: Pinning is best-effort. On some Windows 10/11 builds, scripting this action is blocked.
#>

param(
    [switch]$NoPin,
    [switch]$Hidden
)

$ErrorActionPreference = 'Stop'

function New-StartMenuShortcut {
    param(
        [Parameter(Mandatory)] [string]$ShortcutPath,
        [Parameter(Mandatory)] [string]$Target,
        [Parameter(Mandatory)] [string]$WorkingDirectory,
        [string]$Description = 'Reddit Moderator Bot',
        [string]$IconLocation = 'shell32.dll,21'
    )
    Write-Host "Creating shortcut: $ShortcutPath" -ForegroundColor Cyan
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($ShortcutPath)
    $sc.TargetPath = $Target
    $sc.WorkingDirectory = $WorkingDirectory
    $sc.Description = $Description
    $sc.IconLocation = $IconLocation
    $sc.Save()
}

function Invoke-PinToStart {
    param([Parameter(Mandatory)] [string]$ShortcutPath)
    try {
        $shell = New-Object -ComObject Shell.Application
        $folderPath = Split-Path $ShortcutPath -Parent
        $fileName = Split-Path $ShortcutPath -Leaf
        $folder = $shell.Namespace($folderPath)
        if (-not $folder) { return $false }
        $item = $folder.ParseName($fileName)
        if (-not $item) { return $false }
        $verbs = @($item.Verbs())
        # Look for a pin verb across common locales
        $pinVerb = $verbs | Where-Object { $_.Name -match 'Pin to Start|Pin to Start Menu|Aan Start vastmaken|An Start anheften|固定到「开始」|固定到开始屏幕|Пиновать в меню «Пуск»|Aggiungi a Start|固定到開始畫面|固定到開始|固定到開始功能表' } | Select-Object -First 1
        if ($pinVerb) {
            $pinVerb.DoIt()
            Start-Sleep -Milliseconds 300
            return $true
        }
        return $false
    } catch {
        return $false
    }
}

function Get-StartMenuPaths {
    $userPrograms = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'
    $commonPrograms = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'
    [PSCustomObject]@{ User=$userPrograms; Common=$commonPrograms }
}

$paths = Get-StartMenuPaths
foreach ($p in @($paths.User, $paths.Common)) {
    try {
        if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    } catch {
        # Ignore if we cannot create the common path without admin
    }
}

$shortcutName = 'Reddit Moderator Bot.lnk'
$userShortcut   = Join-Path $paths.User   $shortcutName
$commonShortcut = Join-Path $paths.Common $shortcutName

# Determine target
if ($Hidden) {
    $target = Join-Path $PSScriptRoot 'run_hidden.vbs'
} else {
    $target = Join-Path $PSScriptRoot 'launch_bot.bat'
}

# Create in user profile
New-StartMenuShortcut -ShortcutPath $userShortcut -Target $target -WorkingDirectory $PSScriptRoot
$createdUser = Test-Path $userShortcut
if ($createdUser) { Write-Host "User Start Menu shortcut created at: $userShortcut" -ForegroundColor Green }

# Attempt all-users (may need admin; ignore failures)
try {
    New-StartMenuShortcut -ShortcutPath $commonShortcut -Target $target -WorkingDirectory $PSScriptRoot
    if (Test-Path $commonShortcut) { Write-Host "All Users Start Menu shortcut created at: $commonShortcut" -ForegroundColor Green }
} catch {
    Write-Host "Could not create All Users shortcut (permission likely required)." -ForegroundColor Yellow
}

if (-not $NoPin) {
    # Prefer pinning the user shortcut
    $pinTarget = if (Test-Path $userShortcut) { $userShortcut } elseif (Test-Path $commonShortcut) { $commonShortcut } else { $null }
    if ($pinTarget) {
        $pinned = Invoke-PinToStart -ShortcutPath $pinTarget
        if ($pinned) {
            Write-Host 'Pinned to Start successfully (if supported by this Windows version).' -ForegroundColor Green
        } else {
            Write-Host 'Automatic pin to Start is not supported or failed on this system.' -ForegroundColor Yellow
            Write-Host 'Manual pin: Open Start, find "Reddit Moderator Bot" under All apps, right-click > Pin to Start.' -ForegroundColor Cyan
        }
    }
}
