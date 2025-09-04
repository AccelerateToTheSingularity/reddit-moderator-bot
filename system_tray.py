"""
System Tray Integration for Reddit Moderator Bot
Provides minimize-to-tray functionality with show/hide/exit menu.
"""

import pystray
from PIL import Image, ImageDraw
import threading
from typing import Optional, Callable
import os
import sys

class SystemTrayManager:
    """Manages system tray icon, menu, and window visibility."""
    
    def __init__(self, gui_app):
        self.gui_app = gui_app
        self.icon = None  # type: ignore
        self.tray_thread = None  # type: ignore
        self.running = False
        
    def create_tray_icon(self):
        """Create the system tray icon."""
        # Create a simple icon image
        image = self._create_icon_image()
        
        # Create menu items
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.MenuItem("Hide", self.hide_window),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Bot", self.start_bot, enabled=lambda item: self.gui_app.bot_status.name == "STOPPED"),
            pystray.MenuItem("Stop Bot", self.stop_bot, enabled=lambda item: self.gui_app.bot_status.name in ["RUNNING", "PAUSED"]),
            pystray.MenuItem("Pause Bot", self.pause_bot, enabled=lambda item: self.gui_app.bot_status.name == "RUNNING"),
            pystray.MenuItem("Resume Bot", self.resume_bot, enabled=lambda item: self.gui_app.bot_status.name == "PAUSED"),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Safe Mode", self.toggle_safe_mode, checked=lambda item: self.gui_app.safe_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_application)
        )
        
        # Create the icon
        self.icon = pystray.Icon(
            "reddit_moderator_bot",
            image,
            "Reddit Moderator Bot",
            menu
        )
        
        return self.icon
    
    def _create_icon_image(self):
        """Create a black hammer tray icon on transparent background."""
        width, height = 64, 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Hammer icon: handle and head on transparent background
        # Hammer handle (vertical rectangle)
        handle_x1, handle_y1 = 28, 20
        handle_x2, handle_y2 = 36, 55
        draw.rectangle([handle_x1, handle_y1, handle_x2, handle_y2], fill=(139, 69, 19, 255))  # Brown handle
        
        # Hammer head (horizontal rectangle)
        head_x1, head_y1 = 15, 15
        head_x2, head_y2 = 49, 30
        draw.rectangle([head_x1, head_y1, head_x2, head_y2], fill=(128, 128, 128, 255))  # Gray metal head
        
        # Add some detail lines to the hammer head
        draw.line([(head_x1 + 3, head_y1 + 3), (head_x2 - 3, head_y1 + 3)], fill=(64, 64, 64, 255), width=1)
        draw.line([(head_x1 + 3, head_y2 - 3), (head_x2 - 3, head_y2 - 3)], fill=(64, 64, 64, 255), width=1)

        return image
    
    def start_tray(self):
        """Start the system tray in a separate thread."""
        if self.running:
            return
        
        self.running = True
        self.create_tray_icon()
        
        # Run the tray icon in a separate thread
        self.tray_thread = threading.Thread(target=self._run_tray, daemon=True)
        self.tray_thread.start()
    
    def _run_tray(self):
        """Run the system tray icon."""
        try:
            if self.icon:
                self.icon.run()
        except Exception as e:
            print(f"System tray error: {e}")
    
    def stop_tray(self):
        """Stop the system tray."""
        self.running = False
        if self.icon:
            self.icon.stop()
    
    # Menu action handlers
    def show_window(self, icon=None, item=None):
        """Show the main window."""
        self.gui_app.after(0, self._show_window_safe)
    
    def _show_window_safe(self):
        """Safely show the window in the main thread."""
        self.gui_app.deiconify()
        self.gui_app.state("zoomed")  # Maximize the window
        self.gui_app.lift()
        self.gui_app.focus_force()
    
    def hide_window(self, icon=None, item=None):
        """Hide the main window to system tray."""
        self.gui_app.after(0, self._hide_window_safe)
    
    def _hide_window_safe(self):
        """Safely hide the window in the main thread."""
        self.gui_app.withdraw()
    
    def start_bot(self, icon=None, item=None):
        """Start the bot from tray menu."""
        self.gui_app.after(0, self.gui_app.toggle_bot)
    
    def stop_bot(self, icon=None, item=None):
        """Stop the bot from tray menu."""
        self.gui_app.after(0, self.gui_app.toggle_bot)
    
    def pause_bot(self, icon=None, item=None):
        """Pause the bot from tray menu."""
        self.gui_app.after(0, self.gui_app.toggle_pause)
    
    def resume_bot(self, icon=None, item=None):
        """Resume the bot from tray menu."""
        self.gui_app.after(0, self.gui_app.toggle_pause)
    
    def toggle_safe_mode(self, icon=None, item=None):
        """Toggle safe mode from tray menu."""
        self.gui_app.after(0, self.gui_app.toggle_safe_mode)
    
    def quit_application(self, icon=None, item=None):
        """Quit the entire application."""
        self.gui_app.after(0, self.gui_app.on_closing)
