#!/usr/bin/env python3
"""
Wiki Transparency Manager for Reddit Moderator Bot
Handles automatic updates to subreddit wiki pages with removed comment information.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import praw
from praw.exceptions import RedditAPIException, PRAWException


@dataclass
class WikiEntry:
    """Data structure for a wiki entry representing a removed comment."""
    timestamp: str
    comment_full_text: str
    comment_id: str
    permalink: str
    removal_reason: str
    context_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WikiEntry':
        """Create WikiEntry from dictionary."""
        return cls(**data)


@dataclass
class WikiData:
    """Data structure for wiki page data."""
    entries: List[WikiEntry]
    removal_count: int
    last_updated: str
    last_manual_update: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'entries': [entry.to_dict() for entry in self.entries],
            'removal_count': self.removal_count,
            'last_updated': self.last_updated,
            'last_manual_update': self.last_manual_update
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WikiData':
        """Create WikiData from dictionary."""
        entries = [WikiEntry.from_dict(entry_data) for entry_data in data.get('entries', [])]
        return cls(
            entries=entries,
            removal_count=data.get('removal_count', 0),
            last_updated=data.get('last_updated', ''),
            last_manual_update=data.get('last_manual_update', '')
        )


class WikiTransparencyManager:
    """Manages wiki transparency functionality for removed comments."""
    
    def __init__(self, config, reddit_instance: praw.Reddit, logger=None):
        """Initialize the WikiTransparencyManager.
        
        Args:
            config: Bot configuration object with wiki settings
            reddit_instance: Authenticated Reddit instance
            logger: Logger instance for error reporting
        """
        self.config = config
        self.reddit = reddit_instance
        self.logger = logger or logging.getLogger(__name__)
        
        # Wiki configuration
        self.wiki_enabled = getattr(config, 'wiki_transparency_enabled', False)
        self.wiki_page_name = getattr(config, 'wiki_page_name', 'removed_comments')
        self.auto_update_threshold = getattr(config, 'wiki_auto_update_threshold', 10)
        self.rate_limit_delay = getattr(config, 'wiki_rate_limit_delay', 60)
        
        # Data file paths
        self.data_file = Path(getattr(config, 'wiki_data_file', './data/wiki_data.json'))
        self.counter_file = Path(getattr(config, 'wiki_counter_file', './data/removal_counter.json'))
        
        # Ensure data directory exists
        self.data_file.parent.mkdir(exist_ok=True)
        
        # Load existing data
        self.wiki_data = self._load_wiki_data()
        self.removal_counter = self._load_removal_counter()
        
        # Rate limiting
        self.last_update_time = 0
        
        self.logger.info(f"WikiTransparencyManager initialized - Enabled: {self.wiki_enabled}")
    
    def _load_wiki_data(self) -> WikiData:
        """Load wiki data from JSON file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return WikiData.from_dict(data)
            else:
                return WikiData(entries=[], removal_count=0, last_updated="")
        except Exception as e:
            self.logger.error(f"Error loading wiki data: {e}")
            return WikiData(entries=[], removal_count=0, last_updated="")
    
    def _save_wiki_data(self) -> bool:
        """Save wiki data to JSON file."""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.wiki_data.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Error saving wiki data: {e}")
            return False
    
    def _load_removal_counter(self) -> int:
        """Load removal counter from JSON file."""
        try:
            if self.counter_file.exists():
                with open(self.counter_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('count', 0)
            else:
                return 0
        except Exception as e:
            self.logger.error(f"Error loading removal counter: {e}")
            return 0
    
    def _save_removal_counter(self) -> bool:
        """Save removal counter to JSON file."""
        try:
            data = {
                'count': self.removal_counter,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.counter_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Error saving removal counter: {e}")
            return False
    
    def add_removed_comment(self, comment_text: str, comment_id: str, permalink: str, reason: str) -> bool:
        """Add a removed comment to the wiki data and check for auto-update.
        
        Args:
            comment_text: Full text of the removed comment
            comment_id: Reddit comment ID
            permalink: Permalink to the comment
            reason: Reason for removal
            
        Returns:
            bool: True if successfully added, False otherwise
        """
        if not self.wiki_enabled:
            return False
        
        try:
            # Create wiki entry
            entry = WikiEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                comment_full_text=comment_text,
                comment_id=comment_id,
                permalink=f"https://reddit.com{permalink}" if not permalink.startswith('http') else permalink,
                removal_reason=reason,
                context_url=f"https://reddit.com{permalink}?context=3" if not permalink.startswith('http') else f"{permalink}?context=3"
            )
            
            # Add to wiki data
            self.wiki_data.entries.append(entry)
            self.wiki_data.removal_count += 1
            
            # Increment counter
            self.removal_counter += 1
            
            # Save data
            if not self._save_wiki_data():
                return False
            if not self._save_removal_counter():
                return False
            
            self.logger.info(f"Added removed comment to wiki data: {comment_id}")
            
            # Check for auto-update
            if self.removal_counter >= self.auto_update_threshold:
                self.logger.info(f"Auto-update threshold reached ({self.removal_counter}/{self.auto_update_threshold})")
                if self.update_wiki_page():
                    self.removal_counter = 0  # Reset counter after successful update
                    self._save_removal_counter()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding removed comment to wiki: {e}")
            return False
    
    def _check_rate_limit(self) -> bool:
        """Check if enough time has passed since last update."""
        current_time = time.time()
        if current_time - self.last_update_time < self.rate_limit_delay:
            remaining = self.rate_limit_delay - (current_time - self.last_update_time)
            self.logger.warning(f"Rate limit active. {remaining:.1f} seconds remaining.")
            return False
        return True
    
    def _format_wiki_content(self) -> str:
        """Format wiki content from stored entries."""
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if not self.wiki_data.entries:
            content = ["# Removed Comments"]
            content.append("")
            content.append("No comments have been removed yet.")
            content.append("")
            content.append("---")
            content.append("")
            content.append("## Update Test")
            content.append(f"**Last Wiki Update Test:** {current_time}")
            content.append("")
            content.append("This entry confirms that the wiki update functionality is working correctly.")
            content.append("When comments are removed, they will appear above this test entry.")
            return "\n".join(content)
        
        content = ["# Removed Comments"]
        content.append("")
        content.append(f"**Total Removed:** {self.wiki_data.removal_count}")
        content.append(f"**Last Updated:** {current_time}")
        content.append("")
        content.append("---")
        content.append("")
        
        # Sort entries by timestamp (newest first)
        sorted_entries = sorted(self.wiki_data.entries, key=lambda x: x.timestamp, reverse=True)
        
        for i, entry in enumerate(sorted_entries, 1):
            try:
                # Parse timestamp for display
                timestamp = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                
                content.append(f"## Removed Comment #{i}")
                content.append(f"**Removed:** {formatted_time}")
                content.append(f"**Reason:** {entry.removal_reason}")
                content.append(f"**Context:** [View Thread]({entry.context_url})")
                content.append("")
                content.append("**Comment Text:**")
                content.append("```")
                content.append(entry.comment_full_text)
                content.append("```")
                content.append("")
                content.append("---")
                content.append("")
                
            except Exception as e:
                self.logger.error(f"Error formatting entry {i}: {e}")
                continue
        
        return "\n".join(content)
    
    def update_wiki_page(self, manual: bool = False) -> bool:
        """Update the subreddit wiki page with removed comments.
        
        Args:
            manual: Whether this is a manual update (bypasses some checks)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not self.wiki_enabled:
            self.logger.warning("Wiki transparency is disabled")
            return False
        
        # Check rate limiting (skip for manual updates)
        if not manual and not self._check_rate_limit():
            return False
        
        try:
            # Get subreddit
            subreddit = self.reddit.subreddit(self.config.subreddit_name)
            
            # Format content
            content = self._format_wiki_content()
            
            # Update wiki page
            wiki_page = subreddit.wiki[self.wiki_page_name]
            wiki_page.edit(content=content, reason="Updated removed comments transparency log")
            
            # Update timestamps
            self.wiki_data.last_updated = datetime.now(timezone.utc).isoformat()
            if manual:
                self.wiki_data.last_manual_update = self.wiki_data.last_updated
            
            # Save updated data
            self._save_wiki_data()
            
            # Update rate limiting
            self.last_update_time = time.time()
            
            update_type = "Manual" if manual else "Automatic"
            self.logger.info(f"{update_type} wiki update successful: r/{self.config.subreddit_name}/wiki/{self.wiki_page_name}")
            
            return True
            
        except RedditAPIException as e:
            self.logger.error(f"Reddit API error during wiki update: {e}")
            return False
        except PRAWException as e:
            self.logger.error(f"PRAW error during wiki update: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during wiki update: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of wiki transparency system."""
        return {
            'enabled': self.wiki_enabled,
            'total_entries': len(self.wiki_data.entries),
            'removal_count': self.wiki_data.removal_count,
            'counter_until_update': self.auto_update_threshold - self.removal_counter,
            'last_updated': self.wiki_data.last_updated,
            'last_manual_update': self.wiki_data.last_manual_update,
            'wiki_page_url': f"https://reddit.com/r/{self.config.subreddit_name}/wiki/{self.wiki_page_name}" if self.wiki_enabled else None
        }
    
    def clear_data(self) -> bool:
        """Clear all wiki data (for testing or reset purposes)."""
        try:
            self.wiki_data = WikiData(entries=[], removal_count=0, last_updated="")
            self.removal_counter = 0
            
            self._save_wiki_data()
            self._save_removal_counter()
            
            self.logger.info("Wiki data cleared successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing wiki data: {e}")
            return False