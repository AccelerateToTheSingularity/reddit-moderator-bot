"""
Build Script for Reddit Moderator Bot Desktop Application
Creates a standalone .exe file using PyInstaller.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_directories():
    """Clean up previous build artifacts."""
    print("🧹 Cleaning up previous build artifacts...")
    
    directories_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for directory in directories_to_clean:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"   Removed directory: {directory}")
    
    # Remove .spec files
    for spec_file in Path('.').glob('*.spec'):
        spec_file.unlink()
        print(f"   Removed file: {spec_file}")

def create_pyinstaller_spec():
    """Create a custom PyInstaller spec file for better control."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('prompts.py', '.'),
        ('llm_providers.py', '.'),
        ('moderator_bot.py', '.'),
        ('bot_worker.py', '.'),
        ('gui_config.py', '.'),
        ('system_tray.py', '.'),
    ],
    hiddenimports=[
        'praw',
        'requests',
        'google.generativeai',
        'dotenv',
        'customtkinter',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'threading',
        'queue',
        'json',
        'logging',
        'datetime',
        'pathlib',
        'dataclasses',
        'enum',
        'typing',
        'random',
        'time',
        'os',
        'sys',
        're'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RedditModeratorBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path here if you have one
    version_file=None,
)
'''
    
    with open('reddit_moderator_bot.spec', 'w') as f:
        f.write(spec_content)
    
    print("📝 Created PyInstaller spec file: reddit_moderator_bot.spec")

def build_executable():
    """Build the executable using PyInstaller."""
    print("🔨 Building executable with PyInstaller...")
    
    try:
        # Run PyInstaller with the spec file
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            'reddit_moderator_bot.spec'
        ], check=True, capture_output=True, text=True)
        
        print("✅ Build completed successfully!")
        print(f"   Output: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error code {e.returncode}")
        print(f"   Error output: {e.stderr}")
        return False

def copy_required_files():
    """Copy required files to the dist directory."""
    print("📁 Copying required files to distribution directory...")
    
    dist_dir = Path('dist')
    if not dist_dir.exists():
        print("❌ Distribution directory not found!")
        return False
    
    # Files to copy
    required_files = [
        '.env',
        'README.md',
        'SETUP_GUIDE.md',
        'requirements_gui.txt'
    ]
    
    # Directories to copy
    required_dirs = [
        'logs',
        'data'
    ]
    
    for file_name in required_files:
        if os.path.exists(file_name):
            shutil.copy2(file_name, dist_dir)
            print(f"   Copied: {file_name}")
        else:
            print(f"   Warning: {file_name} not found, skipping...")
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            dest_dir = dist_dir / dir_name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(dir_name, dest_dir)
            print(f"   Copied directory: {dir_name}")
        else:
            # Create empty directories if they don't exist
            (dist_dir / dir_name).mkdir(exist_ok=True)
            print(f"   Created empty directory: {dir_name}")
    
    return True

def create_batch_file():
    """Create a batch file for easy execution."""
    print("📄 Creating batch file for easy execution...")
    
    batch_content = '''@echo off
echo Starting Reddit Moderator Bot...
echo.
echo Make sure you have configured your .env file with Reddit API credentials
echo before running the bot for the first time.
echo.
pause
RedditModeratorBot.exe
'''
    
    with open('dist/Start_Reddit_Moderator_Bot.bat', 'w') as f:
        f.write(batch_content)
    
    print("   Created: Start_Reddit_Moderator_Bot.bat")

def create_readme():
    """Create a README file for the distribution."""
    print("📖 Creating distribution README...")
    
    readme_content = '''# Reddit Moderator Bot - Desktop Application

## Quick Start

1. **Configure the bot:**
   - Edit the `.env` file with your Reddit API credentials
   - Set your subreddit and LLM provider settings

2. **Run the bot:**
   - Double-click `Start_Reddit_Moderator_Bot.bat` OR
   - Double-click `RedditModeratorBot.exe` directly

3. **Using the application:**
   - The bot starts in Safe Mode (no actual comment removal)
   - Use the GUI controls to start/stop/pause the bot
   - View live logs in the main window
   - Removed comments appear in the side panel
   - Minimize to system tray by closing the window
   - Right-click the tray icon for quick controls

## System Tray Features

- **Show/Hide**: Toggle window visibility
- **Bot Controls**: Start, stop, pause, resume from tray
- **Safe Mode**: Toggle safe mode on/off
- **Exit**: Completely close the application

## Files Included

- `RedditModeratorBot.exe` - Main application
- `.env` - Configuration file (edit this!)
- `logs/` - Directory for log files
- `data/` - Directory for bot data
- `README.md` - Original project documentation
- `SETUP_GUIDE.md` - Detailed setup instructions
- `requirements_gui.txt` - Python dependencies (for reference)

## Troubleshooting

If the application doesn't start:
1. Check that your `.env` file is properly configured
2. Ensure you have internet connectivity
3. Check the `logs/moderation.log` file for error messages
4. Make sure your Reddit API credentials are valid

## Support

For issues and updates, visit the project repository or check the documentation.
'''
    
    with open('dist/DISTRIBUTION_README.txt', 'w') as f:
        f.write(readme_content)
    
    print("   Created: DISTRIBUTION_README.txt")

def main():
    """Main build process."""
    print("🚀 Starting Reddit Moderator Bot build process...")
    print("=" * 60)
    
    # Step 1: Clean previous builds
    clean_build_directories()
    print()
    
    # Step 2: Create spec file
    create_pyinstaller_spec()
    print()
    
    # Step 3: Build executable
    if not build_executable():
        print("❌ Build process failed!")
        return False
    print()
    
    # Step 4: Copy required files
    if not copy_required_files():
        print("❌ Failed to copy required files!")
        return False
    print()
    
    # Step 5: Create batch file
    create_batch_file()
    print()
    
    # Step 6: Create distribution README
    create_readme()
    print()
    
    print("=" * 60)
    print("🎉 Build process completed successfully!")
    print()
    print("📦 Your executable is ready in the 'dist' directory:")
    print("   - RedditModeratorBot.exe")
    print("   - Start_Reddit_Moderator_Bot.bat")
    print("   - All required configuration files")
    print()
    print("💡 Next steps:")
    print("   1. Navigate to the 'dist' directory")
    print("   2. Configure the .env file with your Reddit API credentials")
    print("   3. Run Start_Reddit_Moderator_Bot.bat to launch the application")
    print()
    print("🔧 For distribution, you can zip the entire 'dist' directory")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
