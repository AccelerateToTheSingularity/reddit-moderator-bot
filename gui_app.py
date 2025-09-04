"""
Reddit Moderator Bot - Desktop GUI Application
Main application window with live log display, removed comments panel, and control buttons.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext
import threading
import queue
from typing import Optional
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Import GUI configuration
from gui_config import GUIConfig

# Create global config instance
gui_config = GUIConfig()

# Import project modules
from bot_worker import BotWorkerThread
from system_tray import SystemTrayManager
from gui_config import BotStatus
import requests
from dotenv import load_dotenv


class ModeratorGUI(ctk.CTk):
    """Main GUI application window for the Reddit Moderator Bot"""
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("Reddit Moderator Bot")
        self.geometry(f"{gui_config.window_width}x{gui_config.window_height}")
        self.minsize(gui_config.min_width, gui_config.min_height)
        
        # Start maximized
        self.state("zoomed")  # For Windows
        # self.attributes("-zoomed", True)  # For Linux/Mac (alternative)
        
        # Initialize state
        self.bot_status = BotStatus.STOPPED
        self.safe_mode = gui_config.safe_mode  # Load safe mode from config
        self.bot_worker = None
        self.gui_queue = queue.Queue()
        
        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.current_model = "gemini"
        
        # Initialize system tray
        self.tray_manager = SystemTrayManager(self)
        self.tray_manager.start_tray()
        
        # Create GUI layout
        self.setup_layout()
        self.setup_log_display()
        self.setup_removed_comments_panel()
        self.setup_control_buttons()
        self.setup_detailed_status_panel()
        self.setup_status_bar()
        
        # Load cumulative statistics and token usage
        try:
            self.load_cumulative_statistics()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to load cumulative statistics: {e}")
        
        # Load and apply saved settings first, then apply startup behavior
        self.load_and_apply_settings()
        self.apply_startup_settings()
        
        # Start GUI update loop
        self.after(gui_config.gui_update_interval, self.update_gui_from_queue)
        
        # Handle window close event and minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # Handle minimize event to hide to tray
        self.bind("<Unmap>", self.on_minimize)
    
    def setup_layout(self):
        """Create the main layout structure"""
        # Configure grid weights - give much more space to main content
        self.grid_columnconfigure(0, weight=8)  # Main content area (significantly increased)
        self.grid_columnconfigure(1, weight=1)  # Side panel (reduced)
        self.grid_rowconfigure(0, weight=1)     # Main content
        self.grid_rowconfigure(1, weight=0)     # Status bar
        
        # Main content frame (left side) - minimal padding for maximum space
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=(10, 2), pady=2, sticky="nsew")  # Minimal padding
        self.main_frame.grid_columnconfigure(0, weight=1)
        # Adjust row weights to give more space to log display
        self.main_frame.grid_rowconfigure(0, weight=0)  # Control buttons (fixed height)
        self.main_frame.grid_rowconfigure(1, weight=0)  # Log label (fixed height) 
        self.main_frame.grid_rowconfigure(2, weight=1)  # Log display gets ALL remaining space
        
        # Side panel frame (right side) - minimal padding and narrower
        self.side_panel = ctk.CTkFrame(self)
        self.side_panel.grid(row=0, column=1, padx=(2, 10), pady=2, sticky="nsew")  # Minimal padding
        self.side_panel.grid_columnconfigure(0, weight=1)
        self.side_panel.grid_rowconfigure(1, weight=1)  # Comments panel gets most space
    
    def setup_control_buttons(self):
        """Create control buttons in the main frame"""
        # Control buttons frame - reduced vertical padding to minimize space
        self.controls_frame = ctk.CTkFrame(self.main_frame)
        self.controls_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")  # Reduced pady from 10 to 5
        self.controls_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)
        
        # Start/Stop button - reduced height and padding
        self.start_stop_btn = ctk.CTkButton(
            self.controls_frame,
            text="Start Bot",
            command=self.toggle_bot,
            height=35,  # Reduced from 40
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0"
        )
        self.start_stop_btn.grid(row=0, column=0, padx=3, pady=3, sticky="ew")  # Reduced padding
        
        # Pause/Resume button - reduced height and padding
        self.pause_resume_btn = ctk.CTkButton(
            self.controls_frame,
            text="Pause",
            command=self.toggle_pause,
            height=35,  # Reduced from 40
            state="disabled",
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0"
        )
        self.pause_resume_btn.grid(row=0, column=1, padx=3, pady=3, sticky="ew")  # Reduced padding
        
        # Wiki Update button - manual wiki update functionality
        self.wiki_update_btn = ctk.CTkButton(
            self.controls_frame,
            text="Update Wiki",
            command=self.manual_wiki_update,
            height=35,
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            state="disabled"  # Disabled when bot is not running
        )
        self.wiki_update_btn.grid(row=0, column=2, padx=3, pady=3, sticky="ew")
        
        # Safe mode toggle - reduced height and padding
        safe_mode_text = "Safe Mode: ON" if self.safe_mode else "Safe Mode: OFF"
        safe_mode_color = "white"
        safe_mode_hover_color = "#f0f0f0"
        self.safe_mode_btn = ctk.CTkButton(
            self.controls_frame,
            text=safe_mode_text,
            command=self.toggle_safe_mode,
            height=35,  # Reduced from 40
            fg_color=safe_mode_color,
            hover_color=safe_mode_hover_color,
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        self.safe_mode_btn.grid(row=0, column=3, padx=3, pady=3, sticky="ew")  # Reduced padding
        
        # Model selection dropdown - reduced height and padding
        self.model_var = ctk.StringVar(value="deepseek")
        self.model_dropdown = ctk.CTkOptionMenu(
            self.controls_frame,
            values=["ollama", "gemini", "deepseek"],
            variable=self.model_var,
            command=self.on_model_change,
            height=35,  # Reduced from 40
            fg_color="white",
            button_color="#f0f0f0",
            button_hover_color="#e5e5e5",
            text_color="black",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.model_dropdown.grid(row=0, column=4, padx=3, pady=3, sticky="ew")
        
        # Ollama specific model dropdown and refresh
        self.ollama_model_var = ctk.StringVar(value="")
        self.ollama_model_dropdown = ctk.CTkOptionMenu(
            self.controls_frame,
            values=["(click refresh)"],
            variable=self.ollama_model_var,
            command=self.on_ollama_model_change,
            height=35,
            fg_color="white",
            button_color="#f0f0f0",
            button_hover_color="#e5e5e5",
            text_color="black",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.ollama_model_dropdown.grid(row=0, column=5, padx=3, pady=3, sticky="ew")
        self.refresh_ollama_btn = ctk.CTkButton(
            self.controls_frame,
            text="Refresh",
            command=self.refresh_ollama_models,
            height=35,
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.refresh_ollama_btn.grid(row=0, column=6, padx=3, pady=3, sticky="ew")
        
        # Initialize visibility based on selected provider
        self.update_ollama_controls_visibility()
        
        # Settings button - reduced height and padding
        self.settings_btn = ctk.CTkButton(
            self.controls_frame,
            text="Settings",
            command=self.open_settings,
            height=35,  # Reduced from 40
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        self.settings_btn.grid(row=0, column=7, padx=3, pady=3, sticky="ew")  # Reduced padding
    
    def setup_log_display(self):
        """Create the live log display area"""
        # Log display label
        self.log_label = ctk.CTkLabel(
            self.main_frame,
            text="Live Bot Logs",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.header_font_size, weight="bold")
        )
        self.log_label.grid(row=1, column=0, padx=10, pady=(5, 2), sticky="w")  # Reduced padding
        
        # Log display text widget (using standard Tkinter Text for tag support)
        log_frame = tk.Frame(self.main_frame, bg="white")
        log_frame.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_display = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", int(gui_config.log_font_size * 0.84 * 0.9)),
            bg="white",
            fg="black",
            insertbackground="black",
            selectbackground="#cde4ff"
        )
        log_scrollbar = tk.Scrollbar(log_frame, command=self.log_display.yview)
        self.log_display.config(yscrollcommand=log_scrollbar.set)
        
        self.log_display.grid(row=0, column=0, sticky="nsew")
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        # Add initial welcome message
        self.log_to_both("Reddit Moderator Bot - Ready to start")
        self.log_to_both("Click 'Start Bot' to begin monitoring your subreddit")
        self.log_to_both("Safe Mode is ON - no comments will be removed\n" if self.safe_mode else "Safe Mode is OFF - comments will be removed!\n")
    
    def setup_removed_comments_panel(self):
        """Create the removed comments side panel"""
        # Panel label
        self.comments_label = ctk.CTkLabel(
            self.side_panel,
            text="Removed Comments",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.header_font_size, weight="bold")
        )
        self.comments_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        # Comments display text widget (using standard Tkinter Text for tag support)
        comments_frame = tk.Frame(self.side_panel, bg="white")
        comments_frame.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")
        comments_frame.grid_rowconfigure(0, weight=1)
        comments_frame.grid_columnconfigure(0, weight=1)
        
        self.comments_display = tk.Text(
            comments_frame,
            wrap="word",
            font=("Consolas", int(gui_config.log_font_size * 0.84 * 0.9)),
            bg="white",
            fg="black",
            insertbackground="black",
            selectbackground="#cde4ff"
        )
        comments_scrollbar = tk.Scrollbar(comments_frame, command=self.comments_display.yview)
        self.comments_display.config(yscrollcommand=comments_scrollbar.set)
        
        self.comments_display.grid(row=0, column=0, sticky="nsew")
        comments_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Add placeholder text
        self.comments_display.insert("end", "Removed comments will appear here...\n\n")
    
    def setup_detailed_status_panel(self):
        """Create the detailed status panel in the side panel"""
        # Status panel label
        self.status_panel_label = ctk.CTkLabel(
            self.side_panel,
            text="Bot Status & Statistics",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.header_font_size, weight="bold")
        )
        self.status_panel_label.grid(row=2, column=0, padx=10, pady=(10, 5), sticky="w")
        
        # Status details frame
        self.status_details_frame = ctk.CTkFrame(self.side_panel)
        self.status_details_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.status_details_frame.grid_columnconfigure(0, weight=1)
        
        # Model info
        self.model_info_label = ctk.CTkLabel(
            self.status_details_frame,
            text="Model: Gemini 2.5 Flash Lite",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.status_font_size),
            anchor="w"
        )
        self.model_info_label.grid(row=0, column=0, padx=10, pady=2, sticky="ew")
        
        # Token statistics
        self.token_stats_label = ctk.CTkLabel(
            self.status_details_frame,
            text="Input Tokens: 0 | Output: 0",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.status_font_size),
            anchor="w"
        )
        self.token_stats_label.grid(row=1, column=0, padx=10, pady=2, sticky="ew")
        
        # Cost information
        self.cost_label = ctk.CTkLabel(
            self.status_details_frame,
            text="Estimated Cost: $0.0000",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.status_font_size),
            anchor="w"
        )
        self.cost_label.grid(row=2, column=0, padx=10, pady=2, sticky="ew")
        
        # Session info
        self.session_info_label = ctk.CTkLabel(
            self.status_details_frame,
            text="Comments Analyzed: 0",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.status_font_size),
            anchor="w"
        )
        self.session_info_label.grid(row=3, column=0, padx=10, pady=2, sticky="ew")
        
        # Comments removed
        self.removed_count_label = ctk.CTkLabel(
            self.status_details_frame,
            text="Comments Removed: 0",
            font=ctk.CTkFont(family="Segoe UI", size=gui_config.status_font_size),
            anchor="w"
        )
        self.removed_count_label.grid(row=4, column=0, padx=10, pady=2, sticky="ew")
        
        # Initialize counters
        self.comments_analyzed = 0
        self.comments_removed = 0
        
        # Adjust grid weights for the side panel
        self.side_panel.grid_rowconfigure(1, weight=2)  # Comments panel gets more space
        self.side_panel.grid_rowconfigure(3, weight=0)  # Status panel fixed size
    
    def setup_status_bar(self):
        """Create the status bar at the bottom"""
        self.status_frame = ctk.CTkFrame(self, height=40, fg_color="white")
        self.status_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_propagate(False)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text=f"Status: {self.bot_status.value} | Safe Mode: {'ON' if self.safe_mode else 'OFF'} | Model: {self.model_var.get().upper()}",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
    
    def update_gui_from_queue(self):
        """Process messages from bot worker thread and update GUI"""
        try:
            while True:
                message = self.gui_queue.get_nowait()
                self.process_gui_message(message)
        except queue.Empty:
            pass
        
        # Schedule next update
        self.after(gui_config.gui_update_interval, self.update_gui_from_queue)
    
    def is_log_display_at_bottom(self):
        """Check if the log display is currently scrolled to the bottom"""
        # Get the current position of the scrollbar
        current_position = self.log_display.yview()[1]
        # If we're at or very near the bottom (within 1 line), consider it at bottom
        return current_position >= 0.99

    def is_comments_display_at_bottom(self):
        """Check if the comments display is currently scrolled to the bottom"""
        # Get the current position of the scrollbar
        current_position = self.comments_display.yview()[1]
        # If we're at or very near the bottom (within 1 line), consider it at bottom
        return current_position >= 0.99
    
    def is_non_comment_info_line(self, log_text):
        """Check if a log line is a non-comment informational message that should be light grey"""
        # Always keep comment analysis lines in normal color
        if log_text.strip().startswith(("Comment", "Decision:", "  Decision:")):
            return False
        
        # System status messages
        if any(phrase in log_text for phrase in [
            "Next check in",
            "Starting Reddit Moderator Bot",
            "Bot execution finished", 
            "❌ Runtime error",
            "❌ Bot worker error",
            "❌ Wiki update error",
            "❌ Error clearing wiki data",
            "=== Reddit Moderator Bot Starting ===",
            "Monitoring subreddit:",
            "Adaptive delay:",
            "🛡️  SAFE MODE ENABLED",
            "⚠️  LIVE MODE",
            "⏱️  Rate limiting:",
            "⏱️  Waiting",
            "adaptive -",
            "base interval",
            "empty checks)",
            "🔴",  # Error indicator emoji
            "✅",  # Success indicator emoji
            "⏱️"   # Timer emoji
        ]):
            return True
        
        # Additional patterns for non-comment informational lines
        if any(pattern in log_text for pattern in [
            "Status:",
            "Safe Mode",
            "Click 'Start Bot'",
            "Starting bot...",
            "Check every",
            "seconds",
            "Token usage",
            "Initializing",
            "initialized",
            "Connected to",
            "Loading",
            "Loaded",
            "successfully",
            "Model:",
            "Provider:",
            "WikiTransparencyManager"
        ]):
            return True
        
        return False
    
    def log_to_both(self, message, end="\n"):
        """Helper method to log message to both GUI and terminal"""
        # Add to GUI
        self.log_display.insert("end", message + end)
        # Print to terminal
        print(message, end=end)
    
    def process_gui_message(self, message):
        """Process a single message from the bot worker"""
        msg_type = message.get('type')
        
        if msg_type == 'log':
            # Add log message to display
            log_text = message['text']
            permalink = message.get('permalink', '')
            suppress_keep = ("Decision: KEEP - does not violate rules" in log_text)
            
            # Print log message to terminal as well
            print(log_text)
            
            if permalink:
                if suppress_keep:
                    # Suppress this KEEP decision line; do not insert into log
                    pass
                else:
                    import re
                    # Make the static 'Comment:' prefix clickable when present
                    if log_text.startswith("Comment:"):
                        prefix = "Comment:"
                        rest = log_text[len(prefix):]
                        # Insert clickable prefix
                        start_pos = self.log_display.index("end-1c")
                        self.log_display.insert("end", prefix)
                        end_pos = self.log_display.index("end-1c")
                        tag_name = f"log_link_{hash(permalink)}"
                        self.log_display.tag_add(tag_name, start_pos, end_pos)
                        self.log_display.tag_config(tag_name, foreground="blue", underline=True)
                        self.log_display.tag_bind(tag_name, "<Button-1>", lambda e, url=permalink: self.open_link(url))
                        self.log_display.tag_bind(tag_name, "<Enter>", lambda e: self.log_display.configure(cursor="hand2"))
                        self.log_display.tag_bind(tag_name, "<Leave>", lambda e: self.log_display.configure(cursor=""))
                        # Insert the rest of the text normally
                        self.log_display.insert("end", rest + "\n")
                    else:
                        # Check if this is a comment line with format: "Comment {id} ..."
                        match = re.match(r'^(Comment )(\w+)(.*)$', log_text)
                        if match:
                            # Make only the 'Comment' word clickable for consistency
                            comment_id = match.group(2)  # the ID
                            suffix = match.group(3)  # rest of the text (may include ': ...')
                            # Insert clickable 'Comment'
                            start_pos = self.log_display.index("end-1c")
                            self.log_display.insert("end", "Comment")
                            end_pos = self.log_display.index("end-1c")
                            tag_name = f"log_link_{hash(permalink)}"
                            self.log_display.tag_add(tag_name, start_pos, end_pos)
                            self.log_display.tag_config(tag_name, foreground="blue", underline=True)
                            self.log_display.tag_bind(tag_name, "<Button-1>", lambda e, url=permalink: self.open_link(url))
                            self.log_display.tag_bind(tag_name, "<Enter>", lambda e: self.log_display.configure(cursor="hand2"))
                            self.log_display.tag_bind(tag_name, "<Leave>", lambda e: self.log_display.configure(cursor=""))
                            # Insert the remainder of the line normally
                            self.log_display.insert("end", f" {comment_id}{suffix}\n")
                        else:
                            # Not a comment line, make the whole line clickable as fallback
                            start_pos = self.log_display.index("end-1c")
                            self.log_display.insert("end", f"{log_text}\n")
                            end_pos = self.log_display.index("end-1c")
                            tag_name = f"log_link_{hash(permalink)}"
                            self.log_display.tag_add(tag_name, start_pos, end_pos)
                            self.log_display.tag_config(tag_name, foreground="blue", underline=True)
                            self.log_display.tag_bind(tag_name, "<Button-1>", lambda e, url=permalink: self.open_link(url))
                            self.log_display.tag_bind(tag_name, "<Enter>", lambda e: self.log_display.configure(cursor="hand2"))
                            self.log_display.tag_bind(tag_name, "<Leave>", lambda e: self.log_display.configure(cursor=""))
                            
                            # Apply red font if "REMOVE" appears in the log text
                            if "REMOVE" in log_text and "WOULD REMOVE" not in log_text and "SAFE MODE" not in log_text:
                                self.log_display.tag_add("remove_highlight", start_pos, end_pos)
                                self.log_display.tag_config("remove_highlight", foreground="red")
                            # Apply light grey color for non-comment informational messages
                            elif self.is_non_comment_info_line(log_text):
                                self.log_display.tag_add("info_line", start_pos, end_pos)
                                self.log_display.tag_config("info_line", foreground="#808080")
            elif not suppress_keep:
                # No permalink, insert normally
                start_pos = self.log_display.index("end-1c")
                self.log_display.insert("end", f"{log_text}\n")
                end_pos = self.log_display.index("end-1c")
                
                # Apply red font if "REMOVE" appears in the log text
                if "REMOVE" in log_text and "WOULD REMOVE" not in log_text and "SAFE MODE" not in log_text:
                    self.log_display.tag_add("remove_highlight", start_pos, end_pos)
                    self.log_display.tag_config("remove_highlight", foreground="red")
                # Apply light grey color for non-comment informational messages
                elif self.is_non_comment_info_line(log_text):
                    self.log_display.tag_add("info_line", start_pos, end_pos)
                    self.log_display.tag_config("info_line", foreground="#808080")
            
            # Only scroll to end if user was already at the bottom
            if self.is_log_display_at_bottom():
                self.log_display.see("end")
            
            # Check if this is a comment analysis log to update removal counter
            text = log_text
            # Look for the decision line format: "  Decision: KEEP/REMOVE/SKIPPED"
            if text.strip().startswith("Decision:") or "Decision:" in text:
                # Check if it was removed (but not in safe mode)
                if "REMOVE" in text and "WOULD REMOVE" not in text and "SAFE MODE" not in text:
                    self.comments_removed += 1
                self.update_detailed_status()
        
        elif msg_type == 'removed_comment':
            # Add removed comment to side panel
            comment_text = message['comment']
            timestamp = message.get('timestamp', '')
            permalink = message.get('permalink', '')
            comment_id = message.get('comment_id', '')
            
            # Insert timestamp
            self.comments_display.insert("end", f"[{timestamp}]\n")
            
            # If we have a permalink and comment ID, make only the comment ID clickable
            if permalink and comment_id:
                # Insert "Comment " prefix normally
                self.comments_display.insert("end", "Comment ")
                # Insert comment ID as clickable text
                start_pos = self.comments_display.index("end-1c")
                self.comments_display.insert("end", comment_id)
                end_pos = self.comments_display.index("end-1c")
                
                # Configure a tag for the hyperlink
                tag_name = f"link_{hash(permalink)}"
                self.comments_display.tag_add(tag_name, start_pos, end_pos)
                self.comments_display.tag_config(tag_name, foreground="blue", underline=True)
                self.comments_display.tag_bind(tag_name, "<Button-1>", lambda e, url=permalink: self.open_link(url))
                self.comments_display.tag_bind(tag_name, "<Enter>", lambda e: self.comments_display.configure(cursor="hand2"))
                self.comments_display.tag_bind(tag_name, "<Leave>", lambda e: self.comments_display.configure(cursor=""))
                
                # Insert the comment text normally on a new line
                self.comments_display.insert("end", f":\n{comment_text}\n")
            elif permalink:
                # Fallback: make the whole comment text clickable if no comment ID
                start_pos = self.comments_display.index("end-1c")
                self.comments_display.insert("end", f"{comment_text}\n")
                end_pos = self.comments_display.index("end-1c")
                tag_name = f"link_{hash(permalink)}"
                self.comments_display.tag_add(tag_name, start_pos, end_pos)
                self.comments_display.tag_config(tag_name, foreground="blue", underline=True)
                self.comments_display.tag_bind(tag_name, "<Button-1>", lambda e, url=permalink: self.open_link(url))
                self.comments_display.tag_bind(tag_name, "<Enter>", lambda e: self.comments_display.configure(cursor="hand2"))
                self.comments_display.tag_bind(tag_name, "<Leave>", lambda e: self.comments_display.configure(cursor=""))
            else:
                # Insert comment normally if no permalink
                self.comments_display.insert("end", f"{comment_text}\n")
            
            self.comments_display.insert("end", "\n---\n\n")
            # Only scroll to end if user was already at the bottom of the comments panel
            if self.is_comments_display_at_bottom():
                self.comments_display.see("end")
            # Update removed comments counter
            self.comments_removed += 1
            try:
                self.save_cumulative_statistics()
            except Exception as e:
                self.log_to_both(f"Warning: Failed to save cumulative statistics: {e}")
            self.update_detailed_status()
        
        elif msg_type == 'comment_analyzed':
            # Update analyzed comments counter
            self.comments_analyzed += 1
            # Update token counts if provided
            if 'input_tokens' in message:
                self.total_input_tokens += message['input_tokens']
            if 'output_tokens' in message:
                self.total_output_tokens += message['output_tokens']
            try:
                self.save_token_usage()
            except Exception as e:
                self.log_to_both(f"Warning: Failed to save token usage: {e}")
            try:
                self.save_cumulative_statistics()
            except Exception as e:
                self.log_to_both(f"Warning: Failed to save cumulative statistics: {e}")
            self.update_detailed_status()
        
        elif msg_type == 'status':
            # Update bot status
            new_status = BotStatus(message['status'])
            self.update_bot_status(new_status)
    
    def update_bot_status(self, new_status: BotStatus):
        """Update the bot status and GUI elements"""
        self.bot_status = new_status
        
        # Update button states based on status
        if new_status == BotStatus.STOPPED:
            self.start_stop_btn.configure(text="Start Bot", state="normal")
            self.pause_resume_btn.configure(state="disabled")
            self.wiki_update_btn.configure(state="disabled")
        
        elif new_status == BotStatus.RUNNING:
            self.start_stop_btn.configure(text="Stop Bot", state="normal")
            self.pause_resume_btn.configure(text="Pause", state="normal")
            self.wiki_update_btn.configure(state="normal")
        
        elif new_status == BotStatus.PAUSED:
            self.pause_resume_btn.configure(text="Resume", state="normal")
            self.wiki_update_btn.configure(state="normal")
        
        elif new_status in [BotStatus.STARTING, BotStatus.STOPPING]:
            self.start_stop_btn.configure(state="disabled")
            self.wiki_update_btn.configure(state="disabled")
            self.pause_resume_btn.configure(state="disabled")
        
        # Update status bar
        self.update_status_bar()
    
    def update_status_bar(self):
        """Update the status bar text"""
        status_text = f"Status: {self.bot_status.value} | Safe Mode: {'ON' if self.safe_mode else 'OFF'} | Model: {self.model_var.get().upper()}"
        self.status_label.configure(text=status_text)
    
    # Button event handlers
    def toggle_bot(self):
        """Start or stop the bot"""
        if self.bot_status == BotStatus.STOPPED:
            # Start bot worker thread
            self.bot_worker = BotWorkerThread(self.gui_queue, initial_safe_mode=self.safe_mode)
            self.bot_worker.start()
            self.log_to_both("Starting bot...")
            self.log_display.see("end")
        else:
            # Stop bot worker thread
            if self.bot_worker:
                self.bot_worker.stop_bot()
                self.log_to_both("Stopping bot...")
                self.log_display.see("end")
    
    def toggle_pause(self):
        """Pause or resume the bot"""
        if not self.bot_worker:
            return
            
        if self.bot_status == BotStatus.RUNNING:
            self.bot_worker.pause_bot()
        elif self.bot_status == BotStatus.PAUSED:
            self.bot_worker.resume_bot()
    
    def manual_wiki_update(self):
        """Manually trigger a wiki update"""
        if not self.bot_worker or self.bot_status == BotStatus.STOPPED:
            self.log_to_both("❌ Bot must be running to update wiki")
            self.log_display.see("end")
            return
        
        try:
            self.log_to_both("🔄 Initiating manual wiki update...")
            self.log_display.see("end")
            
            # Call the bot worker's manual wiki update method
            success = self.bot_worker.manual_wiki_update()
            
            if success:
                self.log_to_both("✅ Manual wiki update completed successfully")
            else:
                self.log_to_both("❌ Manual wiki update failed")
            
            self.log_display.see("end")
            
        except Exception as e:
            self.log_to_both(f"❌ Wiki update error: {str(e)}")
            self.log_display.see("end")
    
    
    
    def toggle_safe_mode(self):
        """Toggle safe mode on/off"""
        try:
            # Toggle the state
            self.safe_mode = not self.safe_mode
            
            # Update button appearance immediately
            if self.safe_mode:
                self.safe_mode_btn.configure(
                    text="Safe Mode: ON",
                    fg_color="white",
                    hover_color="#f0f0f0"
                )
                log_message = "Safe Mode enabled - no comments will be removed\n"
            else:
                self.safe_mode_btn.configure(
                    text="Safe Mode: OFF",
                    fg_color="white",
                    hover_color="#f0f0f0"
                )
                log_message = "Safe Mode disabled - comments will be removed!\n"
            
            # Force GUI update to ensure button changes are visible immediately
            self.safe_mode_btn.update_idletasks()
            self.update_idletasks()
            
            # Update log display and print to terminal
            self.log_to_both(log_message, end="")
            self.log_display.see("end")
            
            # Update status bar
            self.update_status_bar()
            
            # Save safe mode setting to config with error handling
            try:
                gui_config.update_setting('safe_mode', self.safe_mode)
            except Exception as e:
                self.log_to_both(f"Warning: Failed to save safe mode setting: {e}")
            
            # Update bot worker safe mode setting with error handling
            try:
                if self.bot_worker:
                    self.bot_worker.update_safe_mode(self.safe_mode)
            except Exception as e:
                self.log_to_both(f"Warning: Failed to update bot worker safe mode: {e}")
                
        except Exception as e:
            # If anything fails, revert the state and show error
            self.safe_mode = not self.safe_mode  # Revert
            self.log_to_both(f"Error toggling safe mode: {e}")
            self.log_display.see("end")
    
    def update_detailed_status(self):
        """Update the detailed status panel with current statistics"""
        # Update current model
        self.current_model = self.model_var.get()
        
        # Update model info - get actual model name from environment or bot worker
        if self.current_model == "ollama":
            # Try to get the actual Ollama model name from bot worker/config or environment
            actual_model = None
            try:
                if self.bot_worker and hasattr(self.bot_worker, 'bot') and self.bot_worker.bot:
                    actual_model = getattr(self.bot_worker.bot.config, 'ollama_model', None)
                if not actual_model:
                    from dotenv import load_dotenv
                    import os
                    load_dotenv()
                    actual_model = os.getenv('OLLAMA_MODEL', None)
            except Exception:
                actual_model = None
            model_text = f"Model: Ollama ({actual_model})" if actual_model else "Model: Ollama (Local)"
        elif self.current_model == "gemini":
            # Try to get the actual Gemini model name from environment or bot worker
            actual_model = None
            
            # First try to get from bot worker if available
            if self.bot_worker and hasattr(self.bot_worker, 'bot') and self.bot_worker.bot:
                actual_model = self.bot_worker.bot.config.gemini_model
            else:
                # Fallback: read from environment file directly
                try:
                    from dotenv import load_dotenv
                    import os
                    load_dotenv()
                    actual_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')
                except:
                    actual_model = 'gemini-2.5-flash-lite'  # Default fallback
            
            # Format the model name nicely
            if actual_model:
                if "2.5" in actual_model:
                    if "lite" in actual_model:
                        model_text = "Model: Gemini 2.5 Flash Lite"
                    else:
                        model_text = "Model: Gemini 2.5 Flash"
                elif "1.5" in actual_model:
                    model_text = "Model: Gemini 1.5 Flash"
                else:
                    model_text = f"Model: {actual_model.replace('-', ' ').title()}"
            else:
                model_text = "Model: Gemini (Cloud)"
        elif self.current_model == "deepseek":
            # Try to get the actual DeepSeek model name from environment or bot worker
            actual_model = None
            
            # First try to get from bot worker if available
            if self.bot_worker and hasattr(self.bot_worker, 'bot') and self.bot_worker.bot:
                actual_model = self.bot_worker.bot.config.deepseek_model
            else:
                # Fallback: read from environment file directly
                try:
                    from dotenv import load_dotenv
                    import os
                    load_dotenv()
                    actual_model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
                except:
                    actual_model = 'deepseek-chat'  # Default fallback
            
            # Format the model name nicely
            if actual_model:
                model_text = f"Model: DeepSeek {actual_model.replace('-', ' ').title()}"
            else:
                model_text = "Model: DeepSeek (Cloud)"
        else:
            model_text = f"Model: {self.current_model.title()}"
        self.model_info_label.configure(text=model_text)
        
        # Update token statistics
        self.token_stats_label.configure(
            text=f"Input Tokens: {self.total_input_tokens:,} | Output: {self.total_output_tokens:,}"
        )
        
        # Calculate and update cost
        self.calculate_cost()
        self.cost_label.configure(text=f"Estimated Cost: ${self.total_cost:.4f}")
        
        # Update session statistics
        self.session_info_label.configure(text=f"Comments Analyzed: {self.comments_analyzed}")
        self.removed_count_label.configure(text=f"Comments Removed: {self.comments_removed}")
    
    def calculate_cost(self):
        """Calculate the total cost based on token usage and current pricing"""
        pricing = None
        try:
            if hasattr(gui_config, 'token_pricing') and isinstance(gui_config.token_pricing, dict):
                pricing = gui_config.token_pricing.get(self.current_model)
        except Exception:
            pricing = None

        # Fallback pricing if not configured (kept intentionally approximate)
        if pricing is None:
            fallback = {
                'gemini': {'input': 0.000125, 'output': 0.000375},
                'deepseek': {'input': 0.00014, 'output': 0.00028},
                'ollama': {'input': 0.0, 'output': 0.0},
            }
            pricing = fallback.get(self.current_model, {'input': 0.0, 'output': 0.0})

        input_cost = (self.total_input_tokens / 1000) * float(pricing.get('input', 0.0))
        output_cost = (self.total_output_tokens / 1000) * float(pricing.get('output', 0.0))
        self.total_cost = input_cost + output_cost
    
    def on_model_change(self, selected_model):
        """Handle model selection change"""
        self.log_to_both(f"Model changed to: {selected_model.upper()}")
        self.log_display.see("end")
        self.update_status_bar()
        self.update_detailed_status()  # Update status panel with new model
        
        # Update visibility of Ollama-specific controls based on provider
        try:
            self.update_ollama_controls_visibility()
        except Exception:
            pass
        
        # If switched to Ollama, fetch available models for convenience
        if selected_model == 'ollama':
            try:
                self.refresh_ollama_models()
            except Exception:
                pass
        
        # Update bot worker model setting
        if self.bot_worker:
            self.bot_worker.update_llm_provider(selected_model)
            
        # If Ollama, also ensure we reflect any specific model name currently set
        if selected_model == 'ollama':
            try:
                # Trigger a refresh of detailed status by reading config
                self.update_detailed_status()
            except Exception:
                pass

    def update_ollama_controls_visibility(self):
        """Show/Hide Ollama model controls depending on provider selection."""
        is_ollama = (self.model_var.get() == 'ollama')
        try:
            if is_ollama:
                self.ollama_model_dropdown.grid()
                self.refresh_ollama_btn.grid()
                # Preselect current model if available
                current = None
                try:
                    if self.bot_worker and hasattr(self.bot_worker, 'bot') and self.bot_worker.bot:
                        current = getattr(self.bot_worker.bot.config, 'ollama_model', None)
                    if not current:
                        load_dotenv()
                        current = os.getenv('OLLAMA_MODEL', None)
                except Exception:
                    current = None
                if current:
                    self.ollama_model_var.set(current)
            else:
                self.ollama_model_dropdown.grid_remove()
                self.refresh_ollama_btn.grid_remove()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to update Ollama control visibility: {e}")

    def refresh_ollama_models(self):
        """Fetch available Ollama models from local server and populate dropdown."""
        def worker():
            try:
                # Determine Ollama base URL
                base_url = None
                if self.bot_worker and hasattr(self.bot_worker, 'bot') and self.bot_worker.bot:
                    base_url = getattr(self.bot_worker.bot.config, 'ollama_url', None)
                if not base_url:
                    load_dotenv()
                    base_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
                url = base_url.rstrip('/') + '/api/tags'
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                # Extract model names
                models = []
                if isinstance(data, dict) and 'models' in data and isinstance(data['models'], list):
                    for m in data['models']:
                        name = m.get('name') or m.get('model')
                        if name:
                            models.append(name)
                if not models:
                    models = ["No models found"]
                # Update UI in main thread
                def apply():
                    self.ollama_model_dropdown.configure(values=models)
                    # Try to select current model if present
                    current = self.ollama_model_var.get() or (self.bot_worker.bot.config.ollama_model if (self.bot_worker and self.bot_worker.bot) else None)
                    if current in models:
                        self.ollama_model_var.set(current)
                    else:
                        self.ollama_model_var.set(models[0])
                self.after(0, apply)
                self.log_to_both(f"Ollama models refreshed: {', '.join(models[:10])}{'...' if len(models) > 10 else ''}")
            except Exception as e:
                self.after(0, lambda: self.ollama_model_dropdown.configure(values=["Error fetching models"]))
                self.log_to_both(f"Error fetching Ollama models: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def on_ollama_model_change(self, selected_model: str):
        """Handle Ollama model selection change."""
        if not selected_model or selected_model in ("No models found", "Error fetching models", "(click refresh)"):
            return
        self.log_to_both(f"Ollama model changed to: {selected_model}")
        try:
            if self.bot_worker:
                self.bot_worker.update_ollama_model(selected_model)
            # Update detailed status to reflect the exact model name
            self.update_detailed_status()
        except Exception as e:
            self.log_to_both(f"Failed to set Ollama model: {e}")

    def open_settings(self):
        """Open the settings window"""
        SettingsWindow(self, gui_config)
    
    def apply_startup_settings(self):
        """Apply startup settings when the app launches"""
        print(f"apply_startup_settings called - gui_config.start_minimized: {gui_config.start_minimized}, gui_config.auto_start_bot: {gui_config.auto_start_bot}")
        
        # Handle start minimized
        if gui_config.start_minimized:
            self.after(100, self.withdraw)  # Minimize after a short delay
            self.log_to_both("Started minimized to system tray")
        
        # Handle auto-start bot
        if gui_config.auto_start_bot:
            self.after(2000, self.auto_start_bot)  # Start bot after 2 seconds
    
    def auto_start_bot(self):
        """Automatically start the bot if enabled in settings"""
        if self.bot_status == BotStatus.STOPPED:
            self.log_to_both("Auto-starting bot...")
            self.log_display.see("end")
            self.toggle_bot()
    
    def load_and_apply_settings(self):
        """Load and apply saved settings to ensure proper startup behavior"""
        print(f"load_and_apply_settings called - gui_config.start_minimized: {gui_config.start_minimized}")
        
        # Log that settings were loaded
        if gui_config.auto_start_bot or gui_config.start_minimized or gui_config.start_with_windows:
            settings_loaded = []
            if gui_config.auto_start_bot:
                settings_loaded.append("Auto-start bot")
            if gui_config.start_minimized:
                settings_loaded.append("Start minimized")
            if gui_config.start_with_windows:
                settings_loaded.append("Start with Windows")
            
            self.log_to_both(f"Loaded settings: {', '.join(settings_loaded)}")
        
        # Update the detailed status panel to reflect current settings
        self.update_detailed_status()

    def load_saved_settings(self):
        """Load and apply saved settings to GUI elements"""
        # This method ensures that saved settings are properly reflected in the GUI
        # The settings are already loaded in gui_config, we just need to make sure
        # they're applied to any GUI elements that might need updating
        
        print(f"load_saved_settings called - gui_config.auto_start_bot: {gui_config.auto_start_bot}, gui_config.start_minimized: {gui_config.start_minimized}, gui_config.start_with_windows: {gui_config.start_with_windows}")
        
        # Update the detailed status panel to reflect current settings
        self.update_detailed_status()
        
        # Log that settings were loaded
        if gui_config.auto_start_bot or gui_config.start_minimized or gui_config.start_with_windows:
            settings_loaded = []
            if gui_config.auto_start_bot:
                settings_loaded.append("Auto-start bot")
            if gui_config.start_minimized:
                settings_loaded.append("Start minimized")
            if gui_config.start_with_windows:
                settings_loaded.append("Start with Windows")
            
            self.log_to_both(f"Loaded settings: {', '.join(settings_loaded)}")
    
    
    def on_window_close(self):
        """Handle window close event - minimize to tray"""
        # Minimize to tray instead of closing
        self.withdraw()
    
    def on_minimize(self, event):
        """Handle window minimize event"""
        # Only handle if the event is for this window
        if event.widget == self:
            # Small delay to ensure the window is properly minimized before hiding
            self.after(100, self.withdraw)
    
    def on_closing(self):
        """Handle actual application exit"""
        if self.bot_status in [BotStatus.RUNNING, BotStatus.PAUSED]:
            # Stop bot worker thread gracefully
            if self.bot_worker:
                self.bot_worker.stop_bot()
                # Wait a moment for graceful shutdown
                self.after(1000, self._final_cleanup)
                return
        
        self._final_cleanup()
    
    def _final_cleanup(self):
        """Perform final cleanup and exit"""
        # Persist token usage before exit
        try:
            self.save_token_usage()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to save token usage on exit: {e}")
        
        # Persist cumulative statistics before exit
        try:
            self.save_cumulative_statistics()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to save cumulative statistics on exit: {e}")
        
        # Stop system tray
        if self.tray_manager:
            self.tray_manager.stop_tray()
        
        # Destroy the window
        self.destroy()
    
    def load_token_usage(self):
        """Load cumulative token usage totals from disk if available."""
        try:
            token_path = Path("./logs/token_usage.json")
            if token_path.exists():
                with open(token_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.total_input_tokens = int(data.get('total_input_tokens', self.total_input_tokens))
                    self.total_output_tokens = int(data.get('total_output_tokens', self.total_output_tokens))
                # Recalculate cost based on loaded totals
                self.calculate_cost()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to load token usage: {e}")

    def save_token_usage(self):
        """Persist cumulative token usage totals to disk."""
        try:
            logs_dir = Path("./logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            token_path = logs_dir / "token_usage.json"
            payload = {
                'total_input_tokens': int(self.total_input_tokens),
                'total_output_tokens': int(self.total_output_tokens),
                'total_cost': float(round(self.total_cost, 6)),
                'last_updated': datetime.now().isoformat()
            }
            with open(token_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_to_both(f"Warning: Failed to write token usage: {e}")

    def load_cumulative_statistics(self):
        """Load cumulative comment statistics and token usage from disk."""
        try:
            # Load token usage first
            try:
                self.load_token_usage()
            except Exception as e:
                self.log_to_both(f"Warning: Failed to load token usage while loading statistics: {e}")
            
            # Load comments analyzed/removed
            stats_path = Path("./logs/statistics.json")
            if stats_path.exists():
                with open(stats_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure counters exist before assigning
                    if not hasattr(self, 'comments_analyzed'):
                        self.comments_analyzed = 0
                    if not hasattr(self, 'comments_removed'):
                        self.comments_removed = 0
                    self.comments_analyzed = int(data.get('comments_analyzed', self.comments_analyzed))
                    self.comments_removed = int(data.get('comments_removed', self.comments_removed))
            # update UI to reflect loaded values
            self.update_detailed_status()
        except Exception as e:
            self.log_to_both(f"Warning: Failed to load cumulative statistics: {e}")

    def save_cumulative_statistics(self):
        """Persist cumulative comment statistics to disk."""
        try:
            logs_dir = Path("./logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            stats_path = logs_dir / "statistics.json"
            payload = {
                'comments_analyzed': int(self.comments_analyzed),
                'comments_removed': int(self.comments_removed),
                'last_updated': datetime.now().isoformat()
            }
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_to_both(f"Warning: Failed to write cumulative statistics: {e}")

    def open_link(self, url):
        """Open a URL in the default web browser"""
        import webbrowser
        
        # Handle relative Reddit permalinks
        if url.startswith('/'):
            url = 'https://reddit.com' + url
        
        webbrowser.open(url)


class SettingsWindow(ctk.CTkToplevel):
    """Settings window for configuring startup options"""
    
    def __init__(self, parent, gui_config):
        super().__init__(parent)
        
        self.parent = parent
        self.gui_config = gui_config
        
        # Configure window
        self.title("Settings - Reddit Moderator Bot")
        self.geometry("1100x900")
        self.resizable(False, False)
        
        # Make window modal
        self.transient(parent)
        self.grab_set()
        
        # Center the window
        self.center_window()
        
        # Create GUI elements
        self.setup_settings_ui()
        
        # Load current settings
        self.load_current_settings()
    
    def center_window(self):
        """Center the settings window on the parent window"""
        self.update_idletasks()
        
        # Get parent window position and size
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Calculate center position
        x = parent_x + (parent_width // 2) - (1100 // 2)
        y = parent_y + (parent_height // 2) - (900 // 2)
        
        self.geometry(f"1100x900+{x}+{y}")
    
    def setup_settings_ui(self):
        """Create the settings UI elements"""
        # Main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Startup Settings",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        self.title_label.pack(pady=(10, 20))
        
        # Settings frame
        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Auto-start bot setting
        self.auto_start_frame = ctk.CTkFrame(self.settings_frame)
        self.auto_start_frame.pack(fill="x", padx=15, pady=10)
        
        self.auto_start_var = ctk.BooleanVar()
        self.auto_start_checkbox = ctk.CTkCheckBox(
            self.auto_start_frame,
            text="Auto-start bot when app opens",
            variable=self.auto_start_var,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            command=self.on_auto_start_change
        )
        self.auto_start_checkbox.pack(anchor="w", padx=10, pady=10)
        
        self.auto_start_desc = ctk.CTkLabel(
            self.auto_start_frame,
            text="Automatically starts the moderation bot when the application launches",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="black"
        )
        self.auto_start_desc.pack(anchor="w", padx=30, pady=(0, 10))
        
        # Start minimized setting
        self.start_minimized_frame = ctk.CTkFrame(self.settings_frame)
        self.start_minimized_frame.pack(fill="x", padx=15, pady=10)
        
        self.start_minimized_var = ctk.BooleanVar()
        self.start_minimized_checkbox = ctk.CTkCheckBox(
            self.start_minimized_frame,
            text="Start app minimized to system tray",
            variable=self.start_minimized_var,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            command=self.on_start_minimized_change
        )
        self.start_minimized_checkbox.pack(anchor="w", padx=10, pady=10)
        
        self.start_minimized_desc = ctk.CTkLabel(
            self.start_minimized_frame,
            text="App will start minimized to the system tray instead of showing the window",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="black"
        )
        self.start_minimized_desc.pack(anchor="w", padx=30, pady=(0, 10))
        
        # Start with Windows setting
        self.start_with_windows_frame = ctk.CTkFrame(self.settings_frame)
        self.start_with_windows_frame.pack(fill="x", padx=15, pady=10)
        
        self.start_with_windows_var = ctk.BooleanVar()
        self.start_with_windows_checkbox = ctk.CTkCheckBox(
            self.start_with_windows_frame,
            text="Start with Windows",
            variable=self.start_with_windows_var,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            command=self.on_start_with_windows_change
        )
        self.start_with_windows_checkbox.pack(anchor="w", padx=10, pady=10)
        
        self.start_with_windows_desc = ctk.CTkLabel(
            self.start_with_windows_frame,
            text="Automatically start the app when Windows boots up",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="black"
        )
        self.start_with_windows_desc.pack(anchor="w", padx=30, pady=(0, 10))
        
        # Wiki functionality has been removed
        
        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self.main_frame)
        self.buttons_frame.pack(fill="x", padx=10, pady=(10, 10))
        
        # Save button
        self.save_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Save & Close",
            command=self.save_settings,
            width=120,
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.save_btn.pack(side="right", padx=(5, 10), pady=10)

        # Cancel button
        self.cancel_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Cancel",
            command=self.cancel_settings,
            width=100,
            fg_color="white",
            hover_color="#f0f0f0",
            text_color="black",
            border_width=1,
            border_color="#d0d0d0",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.cancel_btn.pack(side="right", padx=(5, 10), pady=10)
    
    def load_current_settings(self):
        """Load current settings into the UI"""
        print(f"Loading settings - auto_start_bot: {self.gui_config.auto_start_bot}, start_minimized: {self.gui_config.start_minimized}, start_with_windows: {self.gui_config.start_with_windows}")
        self.auto_start_var.set(self.gui_config.auto_start_bot)
        self.start_minimized_var.set(self.gui_config.start_minimized)
        self.start_with_windows_var.set(self.gui_config.start_with_windows)
        # Wiki functionality has been removed
    
    def save_settings(self):
        """Save the settings and close the window"""
        print(f"Saving settings - auto_start_bot: {self.auto_start_var.get()}, start_minimized: {self.start_minimized_var.get()}, start_with_windows: {self.start_with_windows_var.get()}")
        
        # Update configuration
        self.gui_config.update_setting('auto_start_bot', self.auto_start_var.get())
        self.gui_config.update_setting('start_minimized', self.start_minimized_var.get())
        self.gui_config.update_setting('start_with_windows', self.start_with_windows_var.get())
        
        # Wiki functionality has been removed
        
        # Debug: Check what was actually saved
        print(f"After save - gui_config.auto_start_bot: {self.gui_config.auto_start_bot}, gui_config.start_minimized: {self.gui_config.start_minimized}, gui_config.start_with_windows: {self.gui_config.start_with_windows}")
        
        # Handle Windows startup registry setting
        if self.start_with_windows_var.get():
            success = self.gui_config.set_windows_startup(True)
            if not success:
                # Show error message
                error_window = ctk.CTkToplevel(self)
                error_window.title("Error")
                error_window.geometry("300x150")
                error_window.transient(self)
                error_window.grab_set()
                
                error_label = ctk.CTkLabel(
                    error_window,
                    text="Failed to set Windows startup.\nPlease run as administrator.",
                    font=ctk.CTkFont(family="Segoe UI", size=12)
                )
                error_label.pack(expand=True)
                
                ok_btn = ctk.CTkButton(
                    error_window,
                    text="OK",
                    command=error_window.destroy,
                    width=80,
                    font=ctk.CTkFont(family="Segoe UI", size=12)
                )
                ok_btn.pack(pady=10)
                
                return
        else:
            self.gui_config.set_windows_startup(False)
        
        # Log the changes
        self.parent.log_to_both("Settings saved successfully")
        if self.auto_start_var.get():
            self.parent.log_to_both("✓ Auto-start bot enabled")
        if self.start_minimized_var.get():
            self.parent.log_to_both("✓ Start minimized enabled")
        if self.start_with_windows_var.get():
            self.parent.log_to_both("✓ Start with Windows enabled")
        # Wiki functionality has been removed
        self.parent.log_display.see("end")
        
        # Close the window
        self.destroy()
    
    def cancel_settings(self):
        """Cancel and close the window without saving"""
        self.destroy()
    
    def on_auto_start_change(self):
        """Callback when auto-start setting is changed"""
        self.gui_config.update_setting('auto_start_bot', self.auto_start_var.get())
        self.parent.log_to_both(f"Auto-start bot setting updated: {self.auto_start_var.get()}")
        self.parent.log_display.see("end")
    
    def on_start_minimized_change(self):
        """Callback when start minimized setting is changed"""
        self.gui_config.update_setting('start_minimized', self.start_minimized_var.get())
        self.parent.log_to_both(f"Start minimized setting updated: {self.start_minimized_var.get()}")
        self.parent.log_display.see("end")
    
    def on_start_with_windows_change(self):
        """Callback when start with Windows setting is changed"""
        self.gui_config.update_setting('start_with_windows', self.start_with_windows_var.get())
        
        # Handle Windows startup registry setting immediately
        if self.start_with_windows_var.get():
            success = self.gui_config.set_windows_startup(True)
            if success:
                self.parent.log_to_both("Start with Windows enabled")
            else:
                self.parent.log_to_both("Failed to enable Start with Windows")
        else:
            self.gui_config.set_windows_startup(False)
            self.parent.log_to_both("Start with Windows disabled")
        
        self.parent.log_display.see("end")

    # Wiki functionality has been removed


def main():
    """Main entry point for the GUI application"""
    # Create and run the application
    app = ModeratorGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
