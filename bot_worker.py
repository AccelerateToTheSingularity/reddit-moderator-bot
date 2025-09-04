"""
Bot Worker Thread - Background execution of Reddit Moderator Bot
Handles running the bot in a separate thread with GUI communication.
"""

import threading
import queue
import time
from typing import Optional
from gui_config import BotStatus
from moderator_bot import RedditModerator

class BotWorkerThread(threading.Thread):
    """Background thread that runs the Reddit Moderator Bot with GUI communication."""
    
    def __init__(self, gui_queue: queue.Queue, initial_safe_mode: Optional[bool] = None):
        super().__init__(daemon=True)
        self.gui_queue = gui_queue
        self.bot: Optional[RedditModerator] = None
        self.running = False
        self.stop_requested = False
        self.initial_safe_mode = initial_safe_mode
        
    def run(self):
        """Main thread execution - runs the bot loop."""
        try:
            # Send status update to GUI
            self.send_status_update(BotStatus.STARTING)
            self.send_gui_message("log", "Initializing bot...")
            
            # Small delay to ensure GUI processes the STARTING status
            import time
            time.sleep(0.1)
            
            # Initialize the bot with GUI queue
            self.bot = RedditModerator(gui_queue=self.gui_queue)

            # Apply initial safe mode from GUI before startup logs/behavior
            if self.initial_safe_mode is not None:
                try:
                    self.bot.update_safe_mode(self.initial_safe_mode)
                except Exception as e:
                    self.send_gui_message("log", f"Warning: Failed to apply initial safe mode: {e}")
            
            # Start the bot
            if self.bot.start():
                self.running = True
                # Small delay before sending RUNNING status
                time.sleep(0.1)
                self.send_status_update(BotStatus.RUNNING)
                self.send_gui_message("log", "Bot is now running and monitoring comments...")
                
                # Run the main bot loop
                self.bot.run()
                
            else:
                self.send_gui_message("log", "❌ Failed to start bot")
                self.send_status_update(BotStatus.STOPPED)
                return
                
        except Exception as e:
            self.send_gui_message("log", f"❌ Bot worker error: {str(e)}")
            self.send_status_update(BotStatus.STOPPED)
        finally:
            self.running = False
            if not self.stop_requested:
                self.send_gui_message("log", "Bot stopped unexpectedly")
            self.send_status_update(BotStatus.STOPPED)
    
    def stop_bot(self):
        """Stop the bot gracefully."""
        self.stop_requested = True
        if self.bot:
            self.send_status_update(BotStatus.STOPPING)
            self.bot.stop()
        self.running = False
    
    def pause_bot(self):
        """Pause the bot."""
        if self.bot and self.running:
            self.bot.pause()
            self.send_status_update(BotStatus.PAUSED)
    
    def resume_bot(self):
        """Resume the bot."""
        if self.bot and self.running:
            self.bot.resume()
            self.send_status_update(BotStatus.RUNNING)
    
    
    def update_safe_mode(self, safe_mode: bool):
        """Update safe mode setting."""
        if self.bot:
            self.bot.update_safe_mode(safe_mode)
    
    def update_llm_provider(self, provider: str):
        """Update LLM provider setting."""
        if self.bot:
            self.bot.update_llm_provider(provider)
    
    def update_ollama_model(self, model: str):
        """Pass-through to update Ollama model at runtime."""
        if self.bot:
            self.bot.update_ollama_model(model)
    
    def manual_wiki_update(self) -> bool:
        """Manually trigger a wiki update."""
        if self.bot and self.running:
            return self.bot.manual_wiki_update()
        return False

    def is_running(self) -> bool:
        """Check if the bot worker is running."""
        return self.running
    
    def is_paused(self) -> bool:
        """Check if the bot is paused."""
        return self.bot.is_paused() if self.bot else False
    
    def send_gui_message(self, msg_type: str, text: str, **kwargs):
        """Send a message to the GUI queue."""
        message = {'type': msg_type, 'text': text, **kwargs}
        try:
            self.gui_queue.put_nowait(message)
        except queue.Full:
            pass  # Queue is full, ignore message
    
    def send_status_update(self, status: BotStatus):
        """Send a status update to the GUI."""
        self.send_gui_message("status", status.value, status=status.value)
