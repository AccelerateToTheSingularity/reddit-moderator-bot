#!/usr/bin/env python3
"""
Debug script to trace settings issues
"""

import os
import json
from gui_config import GUIConfig

def debug_settings():
    print("Debugging settings persistence issue")
    print("=" * 40)
    
    # Check if settings file exists
    config = GUIConfig()
    print(f"Settings file path: {config.config_file}")
    print(f"Settings file exists: {os.path.exists(config.config_file)}")
    
    # Show current settings
    print("\nCurrent settings in memory:")
    print(f"  auto_start_bot: {config.auto_start_bot}")
    print(f"  start_minimized: {config.start_minimized}")
    print(f"  start_with_windows: {config.start_with_windows}")
    
    # Show settings in file
    if os.path.exists(config.config_file):
        print("\nSettings in file:")
        with open(config.config_file, 'r') as f:
            file_settings = json.load(f)
            print(f"  auto_start_bot: {file_settings.get('auto_start_bot', 'NOT FOUND')}")
            print(f"  start_minimized: {file_settings.get('start_minimized', 'NOT FOUND')}")
            print(f"  start_with_windows: {file_settings.get('start_with_windows', 'NOT FOUND')}")
    
    # Try to update a setting
    print("\nUpdating auto_start_bot to True...")
    config.update_setting('auto_start_bot', True)
    
    # Check what happened
    print("After update:")
    print(f"  auto_start_bot in memory: {config.auto_start_bot}")
    
    # Check file again
    if os.path.exists(config.config_file):
        print("Settings in file after update:")
        with open(config.config_file, 'r') as f:
            file_settings = json.load(f)
            print(f"  auto_start_bot: {file_settings.get('auto_start_bot', 'NOT FOUND')}")
    
    # Create new config instance to simulate restart
    print("\nCreating new config instance (simulating app restart)...")
    config2 = GUIConfig()
    print(f"  auto_start_bot in new instance: {config2.auto_start_bot}")

if __name__ == "__main__":
    debug_settings()
