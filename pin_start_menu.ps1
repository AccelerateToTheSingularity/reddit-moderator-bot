# Attempts to pin the Reddit Moderator Bot Start Menu shortcut to Start.
# Note: On many Windows 10/11 builds, scripting this is restricted. Best-effort only.

$programs = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'
$shortcutPath = Join-Path $programs 'Reddit Moderator Bot.lnk'

if (-not (Test-Path $shortcutPath)) {
    Write-Host 'Start Menu shortcut not found. Run create_start_menu_shortcut.ps1 first.' -ForegroundColor Yellow
    exit 1
}

try {
    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.Namespace((Split-Path $shortcutPath -Parent))
    $item = $folder.ParseName((Split-Path $shortcutPath -Leaf))
    if (-not $item) { throw 'Shortcut not found in Shell namespace.' }
    $verb = @($item.Verbs()) | Where-Object { $_.Name -match 'Pin to Start|Pin to Start Menu|Aan Start vastmaken|An Start anheften|固定到「开始」|固定到开始屏幕|Пиновать в меню «Пуск»|Aggiungi a Start|固定到開始畫面|固定到開始|固定到開始功能表' } | Select-Object -First 1
    if ($verb) {
        $verb.DoIt()
        Write-Host 'Pin command invoked. Verify in Start.' -ForegroundColor Green
        exit 0
    } else {
        Write-Host 'Pin verb not available. Use manual pin via Start menu.' -ForegroundColor Yellow
        exit 2
    }
} catch {
    Write-Host "Failed to pin to Start: $_" -ForegroundColor Red
    exit 3
}
