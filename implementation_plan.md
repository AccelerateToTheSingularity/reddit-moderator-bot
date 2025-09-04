# Implementation Plan

[Overview]
Transform the existing command-line Reddit moderator bot into a standalone Windows desktop application with GUI, system tray integration, and executable packaging.

The current bot is a Python command-line script that monitors subreddits for content that violates community guidelines using local LLM analysis. We will create a modern desktop application using customtkinter for the GUI framework, which provides native-looking widgets on Windows. The application will feature a main window with live log display, a side panel showing removed comments, control buttons for bot operations, and system tray integration for background operation. The core moderation logic will run in a separate thread to maintain GUI responsiveness, and the final application will be packaged as a single .exe file using PyInstaller.

[Types]
Simple data structures for GUI state management and thread communication.

The existing bot classes (BotConfig, RedditModerator, etc.) will be reused with minimal modifications. New simple data structures will include:
- GUI state enums for bot status (STOPPED, RUNNING, PAUSED)
- Message objects for thread-safe communication between bot worker and GUI
- Configuration objects for GUI settings (window size, theme, etc.)

[Files]
File structure modifications to support the desktop application architecture.

**New files to be created:**
- `gui_app.py` - Main GUI application entry point and window management (full path: ./gui_app.py)
- `bot_worker.py` - Background thread wrapper for bot logic (full path: ./bot_worker.py) 
- `system_tray.py` - System tray icon and menu management (full path: ./system_tray.py)
- `gui_config.py` - GUI-specific configuration and settings (full path: ./gui_config.py)
- `requirements_gui.txt` - Additional dependencies for GUI version (full path: ./requirements_gui.txt)
- `build_exe.py` - PyInstaller build script (full path: ./build_exe.py)

**Existing files to be modified:**
- `moderator_bot.py` - Refactor to support GUI integration and thread-safe operation
- `.gitignore` - Add PyInstaller build artifacts (build/, dist/, *.spec)

**Configuration file updates:**
- New GUI-specific environment variables in .env for window settings and appearance

[Functions]
Function modifications to support GUI integration and threading.

**New functions:**
- `create_main_window()` in gui_app.py - Initialize main application window with layout and widgets
- `setup_log_display()` in gui_app.py - Configure scrollable text widget for live log output
- `setup_removed_comments_panel()` in gui_app.py - Create side panel for displaying removed comment text
- `setup_control_buttons()` in gui_app.py - Create and configure start/stop/pause/manual check buttons
- `update_gui_from_queue()` in gui_app.py - Process messages from bot worker thread and update GUI
- `toggle_safe_mode()` in gui_app.py - Handle safe mode on/off button functionality
- `run_bot_loop()` in bot_worker.py - Main bot execution loop adapted for threading
- `send_gui_update()` in bot_worker.py - Send status updates and data to GUI thread
- `create_tray_icon()` in system_tray.py - Initialize system tray icon with menu
- `show_hide_window()` in system_tray.py - Toggle main window visibility from tray

**Modified functions:**
- `main()` in moderator_bot.py - Remove direct execution, make importable
- `log_comment_analysis()` in ModerationLogger - Add GUI message queue output
- `run()` in RedditModerator - Add pause/resume controls and GUI communication

[Classes]
Class modifications to support GUI architecture and thread communication.

**New classes:**
- `ModeratorGUI(customtkinter.CTk)` in gui_app.py - Main application window class with all GUI components and event handlers
- `BotWorkerThread(threading.Thread)` in bot_worker.py - Background thread class that wraps RedditModerator with GUI communication
- `SystemTrayManager` in system_tray.py - Manages system tray icon, menu, and window visibility
- `GUIConfig` in gui_config.py - Configuration class for GUI-specific settings like theme and window size

**Modified classes:**
- `RedditModerator` in moderator_bot.py - Add thread-safe control methods (pause, resume, stop) and GUI message queue integration
- `ModerationLogger` in moderator_bot.py - Extend to send log messages to GUI queue in addition to file/console output

[Dependencies]
New Python packages required for GUI functionality and executable packaging.

- `customtkinter>=5.2.0` - Modern GUI framework with native Windows appearance
- `pyinstaller>=5.13.0` - Package Python application as standalone executable
- `pystray>=0.19.4` - System tray icon support
- `pillow>=10.0.0` - Image processing for tray icons and GUI elements
- `threading` - Built-in Python module for background bot operation
- `queue` - Built-in Python module for thread-safe GUI communication

All existing dependencies (praw, requests, google-generativeai, etc.) will be maintained.

[Testing]
Testing strategy for GUI components and executable packaging.

**Test file requirements:**
- Maintain existing `test_llm.py` for core bot functionality validation
- Create `test_gui.py` for GUI component testing (window creation, button functionality)
- Create `test_threading.py` for bot worker thread communication testing

**Existing test modifications:**
- Ensure `test_llm.py` works with refactored bot classes
- Add GUI integration tests to verify bot-to-GUI communication

**Validation strategies:**
- Manual testing of GUI responsiveness during bot operation
- System tray functionality testing (minimize to tray, restore from tray)
- Executable testing on clean Windows environment without Python installed
- Safe mode toggle testing to ensure no actual comment removal
- Log display testing with high-volume comment processing

[Implementation Order]
Sequential implementation steps to minimize conflicts and ensure successful integration.

1. **Install GUI Dependencies** - Add customtkinter, pyinstaller, pystray to environment and create requirements_gui.txt
2. **Create Basic GUI Structure** - Implement gui_app.py with main window layout, placeholder widgets, and basic event handling
3. **Refactor Bot for Threading** - Modify moderator_bot.py classes to support pause/resume controls and remove direct execution
4. **Implement Bot Worker Thread** - Create bot_worker.py to run bot logic in background with GUI communication via queues
5. **Connect Bot to GUI** - Integrate worker thread with GUI to display live logs and removed comments in real-time
6. **Add Control Button Functionality** - Implement start/stop/pause/manual check/safe mode toggle button handlers
7. **Implement System Tray** - Create system_tray.py for minimize-to-tray functionality with show/hide/exit menu
8. **Create Build Script** - Implement build_exe.py with PyInstaller configuration for single-file executable generation
9. **Package and Test Executable** - Generate .exe file and perform comprehensive testing on clean Windows environment
