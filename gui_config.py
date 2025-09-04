"""
GUI Configuration and Shared Types
Contains configuration classes and enums shared between GUI components.
"""

from enum import Enum
import json
import os
import sys
import winreg

class BotStatus(Enum):
    """Bot operation status states"""
    STOPPED = "Stopped"
    RUNNING = "Running"
    PAUSED = "Paused"
    STARTING = "Starting..."
    STOPPING = "Stopping..."

class GUIConfig:
    """Configuration class for GUI-specific settings"""
    
    def __init__(self):
        # Configuration file path
        self.config_file = os.path.join(os.path.dirname(__file__), 'data', 'gui_settings.json')
        
        # Default settings
        self._default_settings = {
            # Window settings
            'window_width': 1400,
            'window_height': 900,
            'min_width': 1000,
            'min_height': 700,
            
            # Appearance settings
            'appearance_mode': "light",  # "System", "Dark", "Light"
            'color_theme': "blue",       # "blue", "green", "dark-blue"
            
            # Font settings (adjusted per user request)
            'default_font_size': 20,
            'header_font_size': 27,
            'button_font_size': 42,
            'log_font_size': 18,
            'status_font_size': 17,
            
            # Update intervals
            'gui_update_interval': 100,  # milliseconds
            
            # Queue settings
            'max_queue_size': 1000,
            
            # Startup options
            'auto_start_bot': True,
            'start_minimized': True,
            'start_with_windows': True,
            
            # Safe mode setting
            'safe_mode': True,
            
            # Token pricing (as of current date - can be updated)
            'token_pricing': {
                'gemini': {
                    'input': 0.000075,   # $0.075 per 1K tokens for Gemini 1.5 Flash
                    'output': 0.0003     # $0.30 per 1K tokens for Gemini 1.5 Flash
                },
                'ollama': {
                    'input': 0.0,        # Free for local models
                    'output': 0.0        # Free for local models
                },
                'deepseek': {
                    'input': 0.00014,    # $0.00014 per 1K input tokens for DeepSeek
                    'output': 0.00028    # $0.00028 per 1K output tokens for DeepSeek
                }
            },
            
            # Wiki functionality has been removed
        }
        
        # Load settings from file or use defaults
        self._load_settings()
        
        # Set attributes from loaded settings
        for key, value in self.settings.items():
            setattr(self, key, value)
    
    def _load_settings(self):
        """Load settings from JSON file or create with defaults"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Start with a copy of defaults
                    merged = self._default_settings.copy()

                    # Shallow-merge top-level values first
                    for k, v in loaded_settings.items():
                        # We'll deep-merge token_pricing below
                        if k != 'token_pricing':
                            merged[k] = v

                    # Deep-merge token_pricing so saved settings don't wipe new providers
                    try:
                        default_tp = self._default_settings.get('token_pricing', {}) or {}
                        loaded_tp = loaded_settings.get('token_pricing', {}) or {}
                        merged_tp = default_tp.copy()
                        # Merge provider-level dicts
                        for provider, pricing in loaded_tp.items():
                            if isinstance(pricing, dict):
                                base = default_tp.get(provider, {}).copy()
                                base.update(pricing)
                                merged_tp[provider] = base
                            else:
                                # If malformed, prefer default pricing for safety
                                merged_tp[provider] = default_tp.get(provider, pricing)
                        merged['token_pricing'] = merged_tp
                    except Exception:
                        # Fallback to defaults if anything goes wrong
                        merged['token_pricing'] = self._default_settings.get('token_pricing', {})

                    self.settings = merged
            else:
                self.settings = self._default_settings.copy()
                self._save_settings()
        except Exception as e:
            print(f"Error loading GUI settings: {e}")
            self.settings = self._default_settings.copy()
    
    def _save_settings(self):
        """Save current settings to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving GUI settings: {e}")
    
    def update_setting(self, key, value):
        """Update a setting and save to file"""
        if key in self._default_settings:
            setattr(self, key, value)
            self.settings[key] = value
            self._save_settings()
        else:
            print(f"Warning: Unknown setting key '{key}' - ignoring update")
    
    def get_windows_startup_registry_key(self):
        """Get the Windows startup registry key path"""
        return r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    
    def get_app_name_for_registry(self):
        """Get the application name for Windows registry"""
        return "RedditModeratorBot"
    
    def is_windows_startup_enabled(self):
        """Check if the app is set to start with Windows"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.get_windows_startup_registry_key())
            try:
                winreg.QueryValueEx(key, self.get_app_name_for_registry())
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False
    
    def set_windows_startup(self, enabled):
        """Enable or disable Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.get_windows_startup_registry_key(), 0, winreg.KEY_SET_VALUE)
            
            if enabled:
                # Get the current executable path
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable
                    app_path = sys.executable
                else:
                    # Running as Python script
                    app_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                
                winreg.SetValueEx(key, self.get_app_name_for_registry(), 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, self.get_app_name_for_registry())
                except FileNotFoundError:
                    pass  # Key doesn't exist, which is fine
            
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error setting Windows startup: {e}")
            return False
