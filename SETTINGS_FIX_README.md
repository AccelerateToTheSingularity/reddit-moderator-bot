# Settings Persistence Fix

## Issue
Settings were not persisting between application sessions in the Reddit Moderator Bot GUI application.

## Root Cause
The issue was in the `SettingsWindow.save_settings()` method in `gui_app.py`. The method was using the global `gui_config` variable instead of the instance variable `self.gui_config`, which meant that settings changes were not being properly applied to the correct configuration instance.

## Fix Applied

### 1. Updated SettingsWindow.save_settings()
Modified the `save_settings` method to use the instance variable `self.gui_config` instead of the global `gui_config`:

```python
def save_settings(self):
    """Save the settings and close the window"""
    # Update configuration
    self.gui_config.update_setting('auto_start_bot', self.auto_start_var.get())
    self.gui_config.update_setting('start_minimized', self.start_minimized_var.get())
    self.gui_config.update_setting('start_with_windows', self.start_with_windows_var.get())
    
    # Handle Windows startup registry setting
    if self.start_with_windows_var.get():
        success = self.gui_config.set_windows_startup(True)
    else:
        self.gui_config.set_windows_startup(False)
```

## Verification
The fix has been tested and verified with custom test scripts, which confirm that:
1. Settings are properly saved to the JSON file
2. Settings persist between application sessions
3. Settings can be loaded correctly when the application restarts

## Files Modified
- `gui_app.py` - Main fix implementation

The settings persistence issue has been resolved and settings will now correctly persist between application sessions.
