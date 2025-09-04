#!/usr/bin/env python3
"""
Clean up test data for wiki transparency feature
"""

import os
import sys

# Add the current directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moderator_bot import BotConfig
from wiki_transparency import WikiTransparencyManager
import praw
import logging


def clean_test_data():
    """Clean up test data from wiki"""
    print("Cleaning up test data...")
    
    # Load configuration
    config = BotConfig()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize Reddit instance
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret,
            username=config.reddit_username,
            password=config.reddit_password,
            user_agent=config.reddit_user_agent
        )
        
        # Initialize WikiTransparencyManager
        wiki_manager = WikiTransparencyManager(config, reddit, logger)
        
        # Clear all data
        success = wiki_manager.clear_data()
        
        if success:
            print("✅ Test data cleared successfully")
            
            # Update wiki page to remove test content
            wiki_manager.update_wiki_page(manual=True)
            print("✅ Wiki page updated with clean state")
        else:
            print("❌ Failed to clear test data")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")


if __name__ == "__main__":
    clean_test_data()
