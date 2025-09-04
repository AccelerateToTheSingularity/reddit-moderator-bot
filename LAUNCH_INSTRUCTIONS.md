# Reddit Moderator Bot - Launch Instructions

## Easy Ways to Launch the Bot

### Method 1: Double-click the Batch File
1. Simply double-click `launch_bot.bat` in the project folder
2. The bot will start automatically
3. A command window will stay open showing any error messages
4. Press any key to close the command window when done

### Method 2: Create a Desktop Shortcut
1. Right-click on `create_desktop_shortcut.ps1`
2. Select "Run with PowerShell"
3. If prompted, allow the script to run
4. A shortcut named "Reddit Moderator Bot" will appear on your desktop
5. Double-click the desktop shortcut to launch the bot

### Method 3: Pin to Start Menu or Taskbar
1. Right-click on `launch_bot.bat`
2. Select "Pin to Start" or "Pin to taskbar"
3. The bot will be easily accessible from your Start menu or taskbar
4. Click the pinned icon to launch the bot

### Method 4: Run from Command Line
1. Open Command Prompt or PowerShell
2. Navigate to the project folder
3. Run: `python gui_app.py`

## Troubleshooting

### If the batch file doesn't work:
- Make sure Python is installed and added to your PATH
- Try running `python --version` in Command Prompt to verify Python is accessible
- If Python is not found, you may need to reinstall Python with "Add to PATH" option checked

### If you get permission errors:
- Right-click the PowerShell script and select "Run as Administrator"
- Or manually create a shortcut by right-clicking on `launch_bot.bat` and selecting "Create shortcut"

### If the GUI doesn't start:
- Check that all required packages are installed: `pip install -r requirements_gui.txt`
- Make sure your `.env` file is properly configured with Reddit API credentials

## Auto-Start Options

The bot includes built-in options to:
- Auto-start the bot when the application opens
- Start the application minimized to system tray
- Start with Windows (requires administrator privileges)

Access these options through the "Settings" button in the GUI.

## Start Menu Shortcut (and pinning)

To add an entry under Start > All apps and try to pin it to Start:

1. Create the Start Menu shortcut
	- Right-click `create_start_menu_shortcut.ps1` > Run with PowerShell
	- This creates a shortcut named "Reddit Moderator Bot" in your Start Menu > Programs.

2. Pin to Start (best-effort)
	- The same script attempts to pin automatically. On some Windows 10/11 builds, Microsoft blocks scripting this action.
	- If it fails, pin manually: Open Start, scroll to "Reddit Moderator Bot" under All apps, right‑click > Pin to Start.

You can re-run `pin_start_menu.ps1` later to try pinning again.
