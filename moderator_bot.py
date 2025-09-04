#!/usr/bin/env python3
"""
Reddit Moderator Bot with LLM Analysis
Automatically detects and moderates comments using configurable LLM analysis.
"""

import os
import sys
import time
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import praw
import requests
from dotenv import load_dotenv
from prompts import get_content_moderation_prompt, log_prompt_usage, validate_prompt_consistency
from llm_providers import LLMProviderFactory
from wiki_transparency import WikiTransparencyManager

# Load environment variables
load_dotenv()

class BotConfig:
    """Configuration management for the bot."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Reddit API configuration
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.reddit_username = os.getenv('REDDIT_USERNAME')
        self.reddit_password = os.getenv('REDDIT_PASSWORD')
        self.reddit_user_agent = os.getenv('REDDIT_USER_AGENT')
        self.subreddit_name = os.getenv('SUBREDDIT_TO_MONITOR')
        
        # Validate required configuration
        required_vars = {
            'REDDIT_CLIENT_ID': self.reddit_client_id,
            'REDDIT_CLIENT_SECRET': self.reddit_client_secret,
            'REDDIT_USERNAME': self.reddit_username,
            'REDDIT_PASSWORD': self.reddit_password,
            'REDDIT_USER_AGENT': self.reddit_user_agent,
            'SUBREDDIT_TO_MONITOR': self.subreddit_name
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Bot operation settings
        self.check_interval = 3  # seconds
        
        # Adaptive delay configuration
        self.adaptive_base_interval = float(os.getenv('ADAPTIVE_BASE_INTERVAL', '3.0'))  # Base interval in seconds
        self.adaptive_increase_percentage = float(os.getenv('ADAPTIVE_INCREASE_PERCENTAGE', '20.0'))  # Percentage increase per cycle (set to 20%)
        self.adaptive_max_delay = float(os.getenv('ADAPTIVE_MAX_DELAY', '900.0'))  # Maximum delay in seconds (15 minutes)
        
        # Rate limiting configuration - Reddit API protection
        self.max_requests_per_minute = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '4'))  # 4 = 15 seconds between requests (conservative)
        self.min_request_delay = float(os.getenv('MIN_REQUEST_DELAY', '7.0'))  # Minimum 7 seconds between requests (reduced by 3s)
        self.max_request_delay = float(os.getenv('MAX_REQUEST_DELAY', '12.0'))  # Maximum 12 seconds between requests (reduced by 3s)
        self.max_requests_per_hour = 3600
        
        self.llm_retry_attempts = 3
        self.llm_retry_delay = 1  # seconds
        self.llm_timeout = 500  # seconds - increased from 250
        
        # LLM Provider Configuration
        self.llm_provider = os.getenv('LLM_PROVIDER', 'deepseek').lower()
        
        # Ollama configuration (for local models)
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.ollama_host = "localhost:11434"  # Added for compatibility
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'gemma3:latest')
        
        # Gemini configuration (for cloud API)
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_model = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
        
        # DeepSeek configuration (for cloud API)
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.deepseek_model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.deepseek_max_tokens = int(os.getenv('DEEPSEEK_MAX_TOKENS', '1000'))
        self.deepseek_temperature = float(os.getenv('DEEPSEEK_TEMPERATURE', '0.1'))
        self.deepseek_top_p = float(os.getenv('DEEPSEEK_TOP_P', '0.9'))
        self.deepseek_frequency_penalty = float(os.getenv('DEEPSEEK_FREQUENCY_PENALTY', '0.5'))
        self.deepseek_presence_penalty = float(os.getenv('DEEPSEEK_PRESENCE_PENALTY', '0.0'))
        
        # Validate LLM provider configuration
        if self.llm_provider not in ['ollama', 'gemini', 'deepseek']:
            raise ValueError(f"Invalid LLM provider: {self.llm_provider}. Must be 'ollama', 'gemini', or 'deepseek'")
        
        if self.llm_provider == 'gemini' and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")
        
        if self.llm_provider == 'deepseek' and not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when using DeepSeek provider")
        
        # Safe mode configuration
        self.safe_mode = os.getenv('SAFE_MODE', 'true').lower() == 'true'
        
        # File paths
        self.log_file_path = "./logs/moderation.log"
        self.last_check_file = "./data/last_check.json"
        self.removed_comments_only_log = "./logs/removed_comments_only.log"
        self.statistics_log = "./logs/statistics.json"
        
        # Wiki transparency configuration
        self.wiki_transparency_enabled = os.getenv('WIKI_TRANSPARENCY_ENABLED', 'false').lower() == 'true'
        self.wiki_page_name = os.getenv('WIKI_PAGE_NAME', 'removed_comments')
        self.wiki_auto_update_threshold = int(os.getenv('WIKI_AUTO_UPDATE_THRESHOLD', '10'))
        self.wiki_rate_limit_delay = int(os.getenv('WIKI_RATE_LIMIT_DELAY', '60'))
        self.wiki_data_file = os.getenv('WIKI_DATA_FILE', './data/wiki_data.json')
        self.wiki_counter_file = os.getenv('WIKI_COUNTER_FILE', './data/removal_counter.json')
        
        # Logging settings
        self.enable_logging = True

class ModerationLogger:
    """Handles logging for moderation actions and bot operations."""
    
    def __init__(self, config: BotConfig, gui_queue=None, subreddit=None, reddit_instance=None):
        self.config = config
        self.gui_queue = gui_queue
        self.subreddit = subreddit  # Initialize with provided subreddit or None
        self.reddit_instance = reddit_instance
        self.setup_logging()
        
        # ANSI color codes for terminal output
        self.RED = '\033[91m'
        self.GREY = '\033[93m'  # Light yellow for technical info
        self.RESET = '\033[0m'
        self.DIVIDER = '=' * 80
        
        # Initialize statistics tracking attributes
        self.comments_analyzed = 0
        self.comments_removed = 0
        self.comments_would_remove = 0
        
        # Initialize removed_comments and removed_count attributes
        self.removed_comments = []
        self.removed_count = 0
        
        # Initialize WikiTransparencyManager if enabled and reddit instance is available
        self.wiki_manager = None
        if self.reddit_instance and config.wiki_transparency_enabled:
            try:
                self.wiki_manager = WikiTransparencyManager(config, self.reddit_instance, self.logger)
                self.logger.info("WikiTransparencyManager initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize WikiTransparencyManager: {e}")
        
        self.load_statistics()
    
    def setup_logging(self):
        """Setup logging configuration with Unicode support."""
        # Create logs directory if it doesn't exist
        log_dir = Path(self.config.log_file_path).parent
        log_dir.mkdir(exist_ok=True)
        
        # Configure console output to handle UTF-8 (with error handling)
        if sys.platform.startswith('win'):
            import codecs
            try:
                # Check if stdout has buffer attribute before trying to wrap it
                if hasattr(sys.stdout, 'buffer'):
                    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
                if hasattr(sys.stderr, 'buffer'):
                    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')
            except (AttributeError, TypeError):
                # If wrapping fails, stdout/stderr are likely already text streams
                pass
        
        # Configure logging with UTF-8 encoding
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.log_file_path, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_startup(self):
        """Log bot startup."""
        print(f"{self.GREY}=== Reddit Moderator Bot Starting ==={self.RESET}")
        print(f"{self.GREY}Monitoring subreddit: r/{self.config.subreddit_name}{self.RESET}")
        print(f"{self.GREY}Adaptive delay: {self.config.adaptive_base_interval}s base, +{self.config.adaptive_increase_percentage}% increase, {self.config.adaptive_max_delay}s max{self.RESET}")
        if self.config.safe_mode:
            print(f"{self.GREY}🛡️  SAFE MODE ENABLED - No comments will be actually removed{self.RESET}")
        else:
            print(f"{self.GREY}⚠️  LIVE MODE - Comments will be removed if flagged{self.RESET}")
    
    def log_comment_analysis(self, comment_id: str, author: str, decision: str, reason: str = "", comment_text: str = "", permalink: str = ""):
        """Log comment analysis results with Unicode error handling and visual enhancements."""
        
        # Escape newlines and tabs for clean logging (no truncation)
        clean_text = comment_text.replace('\n', '\\n').replace('\t', '\\t')
        
        # Apply red color for REMOVE decisions
        if "REMOVE" in decision.upper():
            colored_decision = f"{self.RED}{decision}{self.RESET}"
        else:
            colored_decision = decision
        
        try:
            if comment_text:
                # Log to file (no color codes) - comment first, then decision
                self.logger.info(f"Comment: \"{clean_text}\"")
                self.logger.info(f"Decision: {decision} {reason}")
                
                # Print to console with color - comment first, then decision (only for REMOVE decisions)
                if "REMOVE" in decision.upper():
                    # Make "Comment:" clickable with full Reddit URL
                    if permalink:
                        reddit_url = f"https://reddit.com{permalink}"
                        print(f"  {self.GREY}Comment:{self.RESET} {reddit_url} \"{clean_text}\"")
                    else:
                        print(f"  {self.GREY}Comment:{self.RESET} \"{clean_text}\"")
                    print(f"  {self.GREY}Decision:{self.RESET} {colored_decision} {self.GREY}{reason}{self.RESET}")
                
                # Send to GUI if available
                if hasattr(self, 'send_gui_message'):
                    self.send_gui_message("log", f"Comment: {clean_text}", permalink=permalink)
                    self.send_gui_message("log", f"Decision: {decision} {reason}", permalink=None)
                    # Also emit side-panel events for the web dashboard
                    try:
                        ts = datetime.now().strftime("%H:%M:%S")
                        # Only count real removals (exclude "WOULD REMOVE" in safe mode)
                        if ("REMOVE" in decision.upper()) and ("WOULD" not in decision.upper()):
                            self.send_gui_message(
                                "removed_comment",
                                comment_id,
                                comment=comment_text,
                                timestamp=ts,
                                permalink=permalink,
                                comment_id=comment_id,
                            )
                        elif ("KEEP" in decision.upper()) or ("APPROVE" in decision.upper()):
                            self.send_gui_message(
                                "approved_comment",
                                comment_id,
                                comment=comment_text,
                                timestamp=ts,
                                permalink=permalink,
                                comment_id=comment_id,
                            )
                    except Exception:
                        # Non-fatal if side-panel emission fails
                        pass
        except Exception as log_error:
            # Fallback logging if there's an issue with the logging itself
            print(f"Logging error: {log_error}")
    
    # Method moved to RedditModerator class
    
    def log_decision(self, decision: str, reason: str, comment_text: str = None, comment_id: str = None, permalink: str = None):
        """Enhanced logging for moderation decisions with detailed formatting and GUI integration."""
        try:
            # Color coding for decisions
            if "REMOVE" in decision.upper():
                colored_decision = f"{self.RED}{decision}{self.RESET}"
            elif "APPROVE" in decision.upper():
                colored_decision = f"{self.GREEN}{decision}{self.RESET}"
            else:
                colored_decision = f"{self.YELLOW}{decision}{self.RESET}"
            
            # Clean text for logging
            clean_text = comment_text.strip() if comment_text else ""
            
            if comment_text:
                # Log to file (no color codes) - comment first, then decision
                self.logger.info(f"Comment: \"{clean_text}\"")
                self.logger.info(f"Decision: {decision} {reason}")
                
                # Print to console with color - comment first, then decision (only for REMOVE decisions)
                if "REMOVE" in decision.upper():
                    if permalink:
                        reddit_url = f"https://reddit.com{permalink}"
                        clickable_url = f"\033]8;;{reddit_url}\033\\{reddit_url}\033]8;;\033\\"
                        print(f"  {self.GREY}Comment:{self.RESET} {clickable_url} \"{self.GREY}{clean_text}{self.RESET}\"")
                    else:
                        print(f"  {self.GREY}Comment:{self.RESET} \"{self.GREY}{clean_text}{self.RESET}\"")
                    print(f"  {self.GREY}Decision:{self.RESET} {colored_decision} {self.GREY}{reason}{self.RESET}")
                
                # Send to GUI if available - make "Comment" clickable with comment ID
                if hasattr(self, 'send_gui_message'):
                    self.send_gui_message("log", f"Comment {comment_id}: {clean_text}", permalink=permalink)
                    self.send_gui_message("log", f"  Decision: {decision} {reason}", permalink=None)
                    
                    # Send removed comment to side panel if it was removed
                    if "REMOVE" in decision.upper():
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        # Send comment text for the side panel
                        self.send_gui_message("removed_comment", comment_id, comment=comment_text, timestamp=timestamp, permalink=permalink, comment_id=comment_id)
                    
                    # Send approved comment to side panel if it was kept/approved
                    elif "KEEP" in decision.upper() or "APPROVE" in decision.upper():
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        # Send comment text for the approved comments side panel
                        self.send_gui_message("approved_comment", comment_id, comment=comment_text, timestamp=timestamp, permalink=permalink, comment_id=comment_id)
                
            else:
                # Log to file (no color codes)
                self.logger.info(f"Decision: {decision} {reason}")
                
                # Print to console with color (only for REMOVE decisions)
                if "REMOVE" in decision.upper():
                    print(f"  {self.GREY}Decision:{self.RESET} {colored_decision} {self.GREY}{reason}{self.RESET}")
                
                # Send to GUI if available
                if hasattr(self, 'send_gui_message'):
                    self.send_gui_message("log", f"  Decision: {decision} {reason}", permalink=permalink)
                
        except UnicodeEncodeError:
            # Replace problematic Unicode characters with safe alternatives
            safe_text = clean_text.encode('ascii', 'replace').decode('ascii')
            safe_reason = reason.encode('ascii', 'replace').decode('ascii')
            if comment_text:
                # Log to file (no color codes) - comment first, then decision
                self.logger.info(f"Comment: \"[Unicode chars replaced] {safe_text}\"")
                self.logger.info(f"Decision: {decision} {safe_reason}")
                
                # Print to console with color - comment first, then decision (only for REMOVE decisions)
                if "REMOVE" in decision.upper():
                    if permalink:
                        reddit_url = f"https://reddit.com{permalink}"
                        clickable_url = f"\033]8;;{reddit_url}\033\\{reddit_url}\033]8;;\033\\"
                        print(f"  {self.GREY}Comment:{self.RESET} {clickable_url} \"{self.GREY}[Unicode chars replaced]{self.RESET} {safe_text}\"")
                    else:
                        print(f"  {self.GREY}Comment:{self.RESET} \"{self.GREY}[Unicode chars replaced]{self.RESET} {safe_text}\"")
                    print(f"  {self.GREY}Decision:{self.RESET} {colored_decision} {self.GREY}{safe_reason}{self.RESET}")
                
                # Send to GUI if available - make "Comment" clickable with comment ID
                if hasattr(self, 'send_gui_message'):
                    self.send_gui_message("log", f"Comment {comment_id}: [Unicode chars replaced] {safe_text}", permalink=permalink)
                    self.send_gui_message("log", f"  Decision: {decision} {safe_reason}", permalink=None)
                    
                    # Send removed comment to side panel if it was removed
                    if "REMOVE" in decision.upper():
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        # Send comment text for the side panel
                        self.send_gui_message("removed_comment", comment_id, comment=safe_text, timestamp=timestamp, permalink=permalink, comment_id=comment_id)
                
            else:
                # Log to file (no color codes)
                self.logger.info(f"Decision: {decision} {safe_reason}")
                
                # Print to console with color (only for REMOVE decisions)
                if "REMOVE" in decision.upper():
                    print(f"  {self.GREY}Decision:{self.RESET} {colored_decision} {self.GREY}{safe_reason}{self.RESET}")
                
                # Send to GUI if available
                if hasattr(self, 'send_gui_message'):
                    self.send_gui_message("log", f"  Decision: {decision} {safe_reason}", permalink=permalink)
        except Exception as log_error:
            # Fallback logging if there's an issue with the logging itself
            print(f"Logging error: {log_error}")
    
    def send_gui_message(self, msg_type: str, text: str, **kwargs):
        """Send a message to the GUI queue if available."""
        if self.gui_queue:
            message = {'type': msg_type, 'text': text, **kwargs}
            try:
                self.gui_queue.put_nowait(message)
            except:
                pass  # Queue might be full, ignore

    # Wiki functionality has been removed

    # Wiki functionality has been removed

    def load_statistics(self):
        """Load statistics from file if it exists."""
        try:
            if Path(self.config.statistics_log).exists():
                with open(self.config.statistics_log, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.comments_analyzed = data.get('comments_analyzed', 0)
                    self.comments_removed = data.get('comments_removed', 0)
        except Exception as e:
            print(f"{self.GREY}Error loading statistics: {e}{self.RESET}")
            self.comments_analyzed = 0
            self.comments_removed = 0

    def save_statistics(self):
        """Save statistics to file."""
        try:
            log_dir = Path(self.config.statistics_log).parent
            log_dir.mkdir(exist_ok=True)
            
            data = {
                'comments_analyzed': self.comments_analyzed,
                'comments_removed': self.comments_removed,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'removal_rate': f"{(self.comments_removed / self.comments_analyzed * 100):.2f}%" if self.comments_analyzed > 0 else "0%"
            }
            
            with open(self.config.statistics_log, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{self.GREY}Error saving statistics: {e}{self.RESET}")

    def log_removed_comment_only(self, comment_text: str):
        """Log removed comment text to the comment-only log file."""
        try:
            log_dir = Path(self.config.removed_comments_only_log).parent
            log_dir.mkdir(exist_ok=True)
            
            with open(self.config.removed_comments_only_log, 'a', encoding='utf-8') as f:
                f.write(comment_text + "\n")
                f.write("---\n\n")
        except Exception as e:
            print(f"{self.GREY}Error writing to removed comments only log: {e}{self.RESET}")

    def add_removed_comment(self, comment_text: str, comment_id: str, permalink: str, reason: str):
        """Add a removed comment to the tracking system."""
        # Add to in-memory tracking
        comment_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'comment_text': comment_text,
            'comment_id': comment_id,
            'permalink': permalink,
            'reason': reason
        }
        
        self.removed_comments.append(comment_data)
        self.removed_count += 1
        
        # Log to comment-only file
        self.log_removed_comment_only(comment_text)
        
        # Add to wiki transparency system if enabled
        if self.wiki_manager:
            try:
                success = self.wiki_manager.add_removed_comment(comment_text, comment_id, permalink, reason)
                if success:
                    self.logger.info(f"Added comment {comment_id} to wiki transparency system")
                else:
                    self.logger.warning(f"Failed to add comment {comment_id} to wiki transparency system")
            except Exception as e:
                self.logger.error(f"Error adding comment to wiki transparency: {e}")
        
        # Update statistics
        self.comments_removed += 1
        self.save_statistics()

    # Wiki functionality has been removed
            
        # Wiki functionality has been removed
                
        # Wiki functionality has been removed

    # Wiki functionality has been removed

    # Wiki functionality has been removed
    

    
    def _categorize_error_with_remediation(self, error, context="general"):
        """Categorize errors and provide specific remediation suggestions with network diagnostics."""
        import socket
        import ssl
        from urllib.parse import urlparse
        
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Initialize result structure
        categorization = {
            'category': 'UNKNOWN',
            'severity': 'MEDIUM',
            'remediation': [],
            'network_diagnostics': {},
            'immediate_actions': [],
            'long_term_actions': []
        }
        
        try:
            # Network connectivity diagnostics
            print("Running network diagnostics for error analysis")
            
            # Test basic connectivity to Reddit
            try:
                socket.create_connection(("www.reddit.com", 443), timeout=10)
                categorization['network_diagnostics']['reddit_connectivity'] = 'PASS'
            except Exception as conn_error:
                categorization['network_diagnostics']['reddit_connectivity'] = f'FAIL: {conn_error}'
            
            # Test SSL connectivity
            try:
                context = ssl.create_default_context()
                with socket.create_connection(("oauth.reddit.com", 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname="oauth.reddit.com") as ssock:
                        categorization['network_diagnostics']['ssl_connectivity'] = 'PASS'
            except Exception as ssl_error:
                categorization['network_diagnostics']['ssl_connectivity'] = f'FAIL: {ssl_error}'
            
            # DNS resolution test
            try:
                socket.gethostbyname("www.reddit.com")
                categorization['network_diagnostics']['dns_resolution'] = 'PASS'
            except Exception as dns_error:
                categorization['network_diagnostics']['dns_resolution'] = f'FAIL: {dns_error}'
            
            # Categorize based on error patterns
            if "permission" in error_str or "forbidden" in error_str or "403" in error_str:
                categorization.update({
                    'category': 'PERMISSION_DENIED',
                    'severity': 'HIGH',
                    'immediate_actions': [
                        'Verify bot account is moderator of target subreddit',
                        'Confirm bot account is not banned or restricted'
                    ],
                    'remediation': [
                        'Add bot as moderator with appropriate permissions',
                        'Verify bot account status and karma requirements',
                        'Test with a different moderator account'
                    ]
                })
            
            elif "not found" in error_str or "404" in error_str or "does not exist" in error_str:
                categorization.update({
                    'category': 'RESOURCE_NOT_FOUND',
                    'severity': 'MEDIUM',
                    'immediate_actions': [
                        'Verify subreddit name is correct',
                        'Check if resource exists and is accessible'
                    ],
                    'remediation': [
                        'Verify subreddit exists and is accessible',
                        'Check resource naming conventions',
                        'Verify permissions for resource access'
                    ]
                })
            
            elif "rate limit" in error_str or "429" in error_str or "too many" in error_str:
                # Use enhanced rate limit handling
                rate_limit_handled = self._handle_rate_limit_with_enhanced_logging(error, context)
                
                categorization.update({
                    'category': 'RATE_LIMITED',
                    'severity': 'MEDIUM',
                    'immediate_actions': [
                        'Enhanced rate limit handling applied automatically',
                        'Progressive backoff delay calculated',
                        'Rate limit statistics updated'
                    ],
                    'remediation': [
                        'Reduce API call frequency',
                        'Implement proper rate limiting in code',
                        'Use batch operations where possible',
                        'Monitor API usage quotas',
                        f'Rate limit handled: {"Yes" if rate_limit_handled else "No"}'
                    ]
                })
            
            elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
                categorization.update({
                    'category': 'NETWORK_CONNECTIVITY',
                    'severity': 'HIGH' if categorization['network_diagnostics']['reddit_connectivity'] != 'PASS' else 'MEDIUM',
                    'immediate_actions': [
                        'Check internet connection',
                        'Verify Reddit is accessible',
                        'Test with different network if possible'
                    ],
                    'remediation': [
                        'Check firewall and proxy settings',
                        'Verify DNS resolution is working',
                        'Test from different network location',
                        'Increase timeout values in code',
                        'Implement retry logic with exponential backoff'
                    ]
                })
            
            elif "ssl" in error_str or "certificate" in error_str or "tls" in error_str:
                categorization.update({
                    'category': 'SSL_CERTIFICATE',
                    'severity': 'HIGH',
                    'immediate_actions': [
                        'Check system date and time',
                        'Update SSL certificates',
                        'Verify TLS version compatibility'
                    ],
                    'remediation': [
                        'Update system SSL certificates',
                        'Check for corporate firewall SSL inspection',
                        'Verify system clock is accurate',
                        'Update Python SSL libraries',
                        'Test with different TLS settings'
                    ]
                })
            
            elif "authentication" in error_str or "invalid" in error_str or "token" in error_str:
                categorization.update({
                    'category': 'AUTHENTICATION_FAILED',
                    'severity': 'HIGH',
                    'immediate_actions': [
                        'Verify Reddit API credentials',
                        'Check if tokens have expired',
                        'Test authentication separately'
                    ],
                    'remediation': [
                        'Regenerate Reddit API credentials',
                        'Verify client ID and secret are correct',
                        'Check username and password',
                        'Ensure 2FA is properly configured',
                        'Test with fresh authentication flow'
                    ]
                })
            
            elif "server" in error_str or "500" in error_str or "502" in error_str or "503" in error_str:
                categorization.update({
                    'category': 'SERVER_ERROR',
                    'severity': 'MEDIUM',
                    'immediate_actions': [
                        'Wait and retry (Reddit server issue)',
                        'Check Reddit status page',
                        'Implement retry with backoff'
                    ],
                    'remediation': [
                        'Monitor Reddit status for outages',
                        'Implement robust retry logic',
                        'Add server error handling',
                        'Consider alternative timing for operations'
                    ]
                })
            
            else:
                # Generic error handling
                categorization.update({
                    'category': 'UNKNOWN_ERROR',
                    'severity': 'MEDIUM',
                    'immediate_actions': [
                        'Review full error message and stack trace',
                        'Check recent code changes',
                        'Test with minimal example'
                    ],
                    'remediation': [
                        'Enable debug logging for more details',
                        'Test individual components separately',
                        'Check for recent API changes',
                        'Review error documentation',
                        'Consider reaching out to support'
                    ]
                })
            
            # Context-specific recommendations (wiki functionality has been removed)
            
            # Log the categorization results
            print(f"Error categorized as {categorization['category']} (severity: {categorization['severity']}, type: {error_type})")
            print(f"Network diagnostics: {categorization['network_diagnostics']}")
            
            return categorization
            
        except Exception as categorization_error:
            print(f"Failed to categorize error: {categorization_error}")
            return {
                'category': 'CATEGORIZATION_FAILED',
                'severity': 'HIGH',
                'remediation': ['Manual investigation required'],
                'network_diagnostics': {},
                'immediate_actions': ['Review error manually'],
                'long_term_actions': ['Fix error categorization system']
            }
    
    def _handle_rate_limit_with_enhanced_logging(self, error, context="general", max_retries=3):
        """Enhanced rate limit detection and handling with comprehensive logging and progressive backoff."""
        try:
            error_str = str(error).lower()
            
            # Initialize rate limit tracking if not exists
            if not hasattr(self, '_rate_limit_tracker'):
                self._rate_limit_tracker = {
                    'consecutive_rate_limits': 0,
                    'total_rate_limits': 0,
                    'last_rate_limit_time': 0,
                    'backoff_multiplier': 1.0,
                    'context_specific_limits': {}
                }
            
            # Detect various rate limit patterns
            rate_limit_indicators = [
                'rate limit', '429', 'too many requests', 'quota exceeded',
                'ratelimit', 'rate_limit', 'requests per', 'try again later',
                'temporarily blocked', 'api limit', 'usage limit',
                'request limit', 'call limit', 'throttled'
            ]
            
            is_rate_limited = any(indicator in error_str for indicator in rate_limit_indicators)
            
            if is_rate_limited:
                import time
                current_time = time.time()
                
                # Update rate limit tracking
                self._rate_limit_tracker['consecutive_rate_limits'] += 1
                self._rate_limit_tracker['total_rate_limits'] += 1
                self._rate_limit_tracker['last_rate_limit_time'] = current_time
                
                # Track context-specific rate limits
                if context not in self._rate_limit_tracker['context_specific_limits']:
                    self._rate_limit_tracker['context_specific_limits'][context] = {
                        'count': 0,
                        'last_occurrence': 0,
                        'backoff_level': 0
                    }
                
                context_tracker = self._rate_limit_tracker['context_specific_limits'][context]
                context_tracker['count'] += 1
                context_tracker['last_occurrence'] = current_time
                context_tracker['backoff_level'] = min(context_tracker['backoff_level'] + 1, 5)
                
                # Calculate progressive backoff delay
                base_delay = 60  # Start with 1 minute
                consecutive_multiplier = min(self._rate_limit_tracker['consecutive_rate_limits'], 5)
                context_multiplier = min(context_tracker['backoff_level'], 3)
                
                # Progressive backoff: 60s, 120s, 240s, 480s, 600s (max 10 minutes)
                delay = min(base_delay * (2 ** (consecutive_multiplier - 1)) * context_multiplier, 600)
                
                # Add some randomization to prevent thundering herd
                import random
                delay = delay + random.uniform(0, delay * 0.1)  # Add up to 10% random variation
                
                # Enhanced logging with detailed rate limit information
                print(f"Rate limit detected in {context} context:")
                print(f"  - Consecutive limits: {self._rate_limit_tracker['consecutive_rate_limits']}")
                print(f"  - Total limits: {self._rate_limit_tracker['total_rate_limits']}")
                print(f"  - Context count: {context_tracker['count']}")
                print(f"  - Backoff level: {context_tracker['backoff_level']}")
                print(f"  - Calculated delay: {round(delay, 1)}s")
                print(f"  - Error: {str(error)[:200]}")
                
                # Log to console with enhanced visibility
                print(f"{self.logger.YELLOW}🚫 RATE LIMIT DETECTED{self.logger.RESET}")
                print(f"{self.logger.GREY}Context: {context}{self.logger.RESET}")
                print(f"{self.logger.GREY}Consecutive rate limits: {self._rate_limit_tracker['consecutive_rate_limits']}{self.logger.RESET}")
                print(f"{self.logger.GREY}Total rate limits (session): {self._rate_limit_tracker['total_rate_limits']}{self.logger.RESET}")
                print(f"{self.logger.GREY}Context-specific count: {context_tracker['count']}{self.logger.RESET}")
                print(f"{self.logger.GREY}Backoff level: {context_tracker['backoff_level']}/5{self.logger.RESET}")
                print(f"{self.logger.YELLOW}⏱️  Waiting {delay:.1f} seconds before retry...{self.logger.RESET}")
                
                # Send GUI update with rate limit information
                self.logger.send_gui_message(
                    "rate_limit_detected",
                    f"Rate limit in {context} - waiting {delay:.1f}s",
                    consecutive_limits=self._rate_limit_tracker['consecutive_rate_limits'],
                    total_limits=self._rate_limit_tracker['total_rate_limits'],
                    delay=delay,
                    context=context
                )
                
                # Perform the backoff delay
                time.sleep(delay)
                
                # Log recovery attempt
                print(f"Rate limit backoff completed, attempting retry for {context}")
                print(f"{self.logger.GREEN}✅ Rate limit backoff completed - retrying {context} operation{self.logger.RESET}")
                
                return True  # Indicates rate limit was handled
            
            else:
                # Reset consecutive rate limits if this wasn't a rate limit error
                if self._rate_limit_tracker['consecutive_rate_limits'] > 0:
                    print("Rate limit streak broken - resetting backoff multiplier")
                    self._rate_limit_tracker['consecutive_rate_limits'] = 0
                    self._rate_limit_tracker['backoff_multiplier'] = 1.0
                
                return False  # Not a rate limit error
                
        except Exception as handling_error:
            print(f"Failed to handle rate limit: {handling_error}")
            # Fallback: simple delay if rate limit handling fails
            if any(indicator in str(error).lower() for indicator in ['rate limit', '429', 'too many']):
                print(f"{self.logger.YELLOW}⏱️  Fallback rate limit handling - waiting 60 seconds{self.logger.RESET}")
                time.sleep(60)
                return True
            return False
    
    def _get_rate_limit_statistics(self):
        """Get current rate limit statistics for monitoring and debugging."""
        if not hasattr(self, '_rate_limit_tracker'):
            return {
                'total_rate_limits': 0,
                'consecutive_rate_limits': 0,
                'context_breakdown': {},
                'current_backoff_level': 0
            }
        
        return {
            'total_rate_limits': self._rate_limit_tracker['total_rate_limits'],
            'consecutive_rate_limits': self._rate_limit_tracker['consecutive_rate_limits'],
            'context_breakdown': self._rate_limit_tracker['context_specific_limits'],
            'current_backoff_level': max([ctx.get('backoff_level', 0) for ctx in self._rate_limit_tracker['context_specific_limits'].values()] + [0]),
            'last_rate_limit_time': self._rate_limit_tracker.get('last_rate_limit_time', 0)
        }
    
    def log_moderation_action(self, comment_id: str, author: str, action: str):
        """Log moderation actions with visual enhancements."""
        # Apply red color for REMOVE actions
        if "REMOVE" in action.upper():
            colored_action = f"{self.RED}{action}{self.RESET}"
        else:
            colored_action = action
        
        # Log to file (no color codes)
        self.logger.warning(f"MODERATION: {action} comment {comment_id} by u/{author}")
        
        # Print to console with color
        print(f"{self.GREY}MODERATION:{self.RESET} {colored_action} {self.GREY}comment {comment_id}{self.RESET} by u/{author}")
    
    def log_error(self, error_type: str, message: str):
        """Log errors with Unicode error handling."""
        try:
            self.logger.error(f"{error_type}: {message}")
        except UnicodeEncodeError:
            # Replace problematic Unicode characters with safe alternatives
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            self.logger.error(f"{error_type}: [Unicode chars replaced] {safe_message}")

    def log_api_error(self, error_type: str, message: str, retry_delay: float = None, attempt: int = None):
        """Log API errors with enhanced visibility and retry information."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create formatted message with timestamp and visual indicators
        formatted_message = f"[{timestamp}] 🔴 {error_type.upper()}: {message}"
        
        if retry_delay is not None:
            formatted_message += f" - Retrying in {retry_delay:.1f}s"
        if attempt is not None:
            formatted_message += f" (attempt {attempt})"
        
        # Log to file (no emojis or colors)
        file_message = f"[{timestamp}] {error_type}: {message}"
        if retry_delay is not None:
            file_message += f" - Retrying in {retry_delay:.1f}s"
        if attempt is not None:
            file_message += f" (attempt {attempt})"
        
        self.logger.error(file_message)
        
        # Print to console with red color for high visibility
        print(f"{self.RED}{formatted_message}{self.RESET}")
        
        # Send to GUI if available
        self.send_gui_message("log", formatted_message, permalink=None)
    
    def log_info(self, message: str):
        """Log general information with Unicode error handling."""
        try:
            self.logger.info(message)
        except UnicodeEncodeError:
            # Replace problematic Unicode characters with safe alternatives
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            self.logger.info(f"[Unicode chars replaced] {safe_message}")

class TimestampManager:
    """Manages the last check timestamp for analyzing comments since last run."""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.data_dir = Path(config.last_check_file).parent
        self.data_dir.mkdir(exist_ok=True)
    
    def get_last_check_time(self) -> Optional[datetime]:
        """Get the timestamp of the last check."""
        try:
            if Path(self.config.last_check_file).exists():
                with open(self.config.last_check_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
        except Exception as e:
            print(f"\033[93mError reading last check time: {e}\033[0m")
        return None
    
    def set_historical_timestamp(self):
        """Set the last check time to one month ago for historical testing."""
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        self.update_last_check_time(one_month_ago)
        print(f"\033[93mSet historical timestamp to: {one_month_ago}\033[0m")
    
    def reset_to_current_time(self):
        """Reset the last check time to current time for live comment processing."""
        current_time = datetime.now(timezone.utc)
        self.update_last_check_time(current_time)
        print(f"\033[92mReset timestamp to current time: {current_time}\033[0m")
    
    def update_last_check_time(self, timestamp: datetime):
        """Update the last check timestamp."""
        try:
            data = {'last_check': timestamp.isoformat()}
            with open(self.config.last_check_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"\033[93mError updating last check time: {e}\033[0m")

class AdaptiveDelayManager:
    """Manages adaptive delay for API calls based on activity levels."""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.current_delay = config.adaptive_base_interval
        self.base_interval = config.adaptive_base_interval
        self.increase_percentage = config.adaptive_increase_percentage
        self.max_delay = config.adaptive_max_delay
        self.consecutive_empty_checks = 0
    
    def get_current_delay(self) -> float:
        """Get the current delay interval."""
        return self.current_delay
    
    def increase_delay(self):
        """Increase the delay when no new comments are found."""
        self.consecutive_empty_checks += 1
        if self.current_delay < self.max_delay:
            # Increase delay by the configured percentage
            new_delay = self.current_delay * (1 + self.increase_percentage / 100)
            self.current_delay = min(new_delay, self.max_delay)
    
    def reset_delay(self):
        """Reset delay to base interval when new comments are found."""
        if self.consecutive_empty_checks > 0:
            self.consecutive_empty_checks = 0
            self.current_delay = self.base_interval
    
    def is_at_base_interval(self) -> bool:
        """Check if we're currently at the base interval."""
        return self.current_delay == self.base_interval
    
    def get_status_info(self) -> dict:
        """Get current status information for logging."""
        return {
            'current_delay': self.current_delay,
            'consecutive_empty_checks': self.consecutive_empty_checks,
            'is_at_base': self.is_at_base_interval(),
            'base_interval': self.base_interval,
            'max_delay': self.max_delay
        }

class RateLimiter:
    """Conservative rate limiter for Reddit API calls with minimum delay enforcement."""
    
    def __init__(self, config: BotConfig, logger: ModerationLogger = None):
        self.config = config
        self.logger = logger
        self.request_times = []
        self.last_request_time = 0
    
    def wait_if_needed(self):
        """Wait with random delay between min and max request delay for natural behavior."""
        now = time.time()
        
        # Generate random delay between min and max request delay
        random_delay = random.uniform(self.config.min_request_delay, self.config.max_request_delay)
        
        # Enforce random delay between requests (most important for Reddit API safety)
        time_since_last = now - self.last_request_time
        if time_since_last < random_delay:
            sleep_time = random_delay - time_since_last
            grey = self.logger.GREY if self.logger else '\033[93m'
            reset = self.logger.RESET if self.logger else '\033[0m'
            print(f"{grey}⏱️  Rate limiting: waiting {sleep_time:.1f} seconds (random delay {random_delay:.1f}s){reset}")
            time.sleep(sleep_time)
            now = time.time()  # Update now after sleep
        
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # Check per-minute rate limit as secondary protection
        if len(self.request_times) >= self.config.max_requests_per_minute:
            sleep_time = 60 - (now - self.request_times[0])
            if sleep_time > 0:
                grey = self.logger.GREY if self.logger else '\033[93m'
                reset = self.logger.RESET if self.logger else '\033[0m'
                print(f"{grey}⏱️  Rate limiting: waiting {sleep_time:.1f} seconds (per-minute limit){reset}")
                time.sleep(sleep_time)
                now = time.time()  # Update now after sleep
        
        # Record this request
        self.request_times.append(now)
        self.last_request_time = now

class LLMAnalyzer:
    """Handles LLM analysis of comments using configurable providers."""
    
    def __init__(self, config: BotConfig, logger: ModerationLogger):
        self.config = config
        self.logger = logger
        
        # Validate prompt consistency on startup
        if not validate_prompt_consistency():
            raise ValueError("Prompt validation failed - check logs for details")
        
        # Load centralized prompt
        self.system_prompt = get_content_moderation_prompt()
        log_prompt_usage("moderator_bot")
        
        # Initialize LLM provider based on configuration
        try:
            self.provider = LLMProviderFactory.create_provider(config, logger)
            print(f"{self.logger.GREY}✅ LLM provider '{config.llm_provider}' initialized successfully{self.logger.RESET}")
        except Exception as e:
            self.logger.log_error("LLM Provider", f"Failed to initialize provider: {str(e)}")
            raise
    

    

    
    def analyze_comment(self, comment_text: str, max_retries: int = 3) -> Optional[str]:
        """Analyze a comment using the configured LLM provider. Returns 'REMOVE', 'KEEP', or None if failed."""
        prompt = f"{self.system_prompt}\n\nComment to analyze: {comment_text}"
        
        try:
            full_response, token_info = self.provider.analyze(prompt, comment_text)
            
            if full_response is None:
                self.logger.log_error("LLM Analysis", "Provider returned None response")
                return None
            
            # Extract decision from the response using multiple parsing methods
            decision = self._extract_decision(full_response)
            
            if decision is None:
                self.logger.log_error("LLM Analysis", f"Invalid response format: {full_response}")
                return None
            
            # Log token usage and cost
            self._log_token_usage(token_info)
            
            # Log the full reasoning for audit purposes
            print(f"{self.logger.GREY}LLM reasoning:{self.logger.RESET} {full_response}")
            return decision
            
        except Exception as e:
            self.logger.log_error("LLM Analysis", f"Provider analysis failed: {str(e)}")
            return None
    
    def _log_token_usage(self, token_info: dict):
        """Log token usage and cost information (internal tracking only, no console output)."""
        input_tokens = token_info.get('input_tokens', 0)
        output_tokens = token_info.get('output_tokens', 0)
        total_tokens = token_info.get('total_tokens', 0)
        estimated_cost = token_info.get('estimated_cost', 0.0)
        
        # Send token information for GUI tracking only (no console output)
        self.logger.send_gui_message("comment_analyzed", "Token usage updated", input_tokens=input_tokens, output_tokens=output_tokens)
    
    def _extract_decision(self, response_text: str) -> Optional[str]:
        """Extract REMOVE/KEEP decision from LLM response using multiple parsing methods."""
        import re
        
        # Normalize the response text
        text = response_text.strip().upper()
        
        # Define comprehensive patterns for REMOVE and KEEP variations
        remove_base_patterns = [
            r'REMOV(E|ED|ING|AL|ES)',  # remove, removed, removing, removal, removes
            r'DELET(E|ED|ING|ION)',    # delete, deleted, deleting, deletion
            r'BAN(NED|NING)?',         # ban, banned, banning
            r'BLOCK(ED|ING)?',         # block, blocked, blocking
            r'ELIMINAT(E|ED|ING|ION)'  # eliminate, eliminated, eliminating, elimination
        ]
        
        keep_base_patterns = [
            r'KEEP(S|ING|ER)?',        # keep, keeps, keeping, keeper
            r'KEPT',                   # kept
            r'RETAIN(ED|ING|S)?',      # retain, retained, retaining, retains
            r'ALLOW(ED|ING|S)?',       # allow, allowed, allowing, allows
            r'APPROV(E|ED|ING|AL)',    # approve, approved, approving, approval
            r'ACCEPT(ED|ING|S)?',      # accept, accepted, accepting, accepts
            r'PERMIT(TED|TING|S)?'     # permit, permitted, permitting, permits
        ]
        
        # Track if we found a formal decision to avoid position-based override
        formal_decision_found = False
        
        # Method 1: Look for standard "DECISION: REMOVE/KEEP" format with variations
        for pattern in remove_base_patterns:
            decision_match = re.search(rf'DECISION\s*:\s*({pattern})', text)
            if decision_match:
                formal_decision_found = True
                return 'REMOVE'
        
        for pattern in keep_base_patterns:
            decision_match = re.search(rf'DECISION\s*:\s*({pattern})', text)
            if decision_match:
                formal_decision_found = True
                return 'KEEP'
        
        # Method 2: Look for "DECISION REMOVE/KEEP" (without colon) with variations
        for pattern in remove_base_patterns:
            decision_match = re.search(rf'DECISION\s+({pattern})', text)
            if decision_match:
                formal_decision_found = True
                return 'REMOVE'
        
        for pattern in keep_base_patterns:
            decision_match = re.search(rf'DECISION\s+({pattern})', text)
            if decision_match:
                formal_decision_found = True
                return 'KEEP'
        
        # Method 3: Look for variations at the end of response
        for pattern in remove_base_patterns:
            end_match = re.search(rf'\b({pattern})\s*$', text)
            if end_match:
                return 'REMOVE'
        
        for pattern in keep_base_patterns:
            end_match = re.search(rf'\b({pattern})\s*$', text)
            if end_match:
                return 'KEEP'
        
        # Method 4: Look for variations anywhere in the last line
        lines = text.split('\n')
        if lines:
            last_line = lines[-1].strip()
            
            for pattern in remove_base_patterns:
                last_line_match = re.search(rf'\b({pattern})\b', last_line)
                if last_line_match:
                    return 'REMOVE'
            
            for pattern in keep_base_patterns:
                last_line_match = re.search(rf'\b({pattern})\b', last_line)
                if last_line_match:
                    return 'KEEP'
        
        # Method 5: Look for any occurrence with position-based priority
        # Only use this method if no formal "DECISION:" pattern was found above
        if not formal_decision_found:
            # Check positions to determine which comes last (final decision)
            remove_matches = []
            keep_matches = []
            
            for pattern in remove_base_patterns:
                remove_matches.extend(list(re.finditer(rf'\b({pattern})\b', text)))
            
            for pattern in keep_base_patterns:
                keep_matches.extend(list(re.finditer(rf'\b({pattern})\b', text)))
            
            if remove_matches and keep_matches:
                # If both appear, use the one that appears last
                last_remove = max(match.start() for match in remove_matches)
                last_keep = max(match.start() for match in keep_matches)
                return 'REMOVE' if last_remove > last_keep else 'KEEP'
            elif remove_matches:
                return 'REMOVE'
            elif keep_matches:
                return 'KEEP'
        
        # Method 6: Check for modal and complex phrase patterns
        modal_remove_patterns = [
            r'(SHOULD|MUST|WILL|NEED TO|OUGHT TO)\s+(BE\s+)?(REMOV|DELET|BAN)',
            r'(BEEN|WAS|IS)\s+(REMOV|DELET|BAN)',
            r'(REMOV|DELET|BAN)\s+(IT|THIS|THAT)',
            r'\b(NEEDS?|REQUIRES?)\s+(REMOV|DELET)',
            r'\b(GET\s+RID\s+OF|TAKE\s+DOWN|PULL\s+DOWN)\b'
        ]
        
        modal_keep_patterns = [
            r'(SHOULD|MUST|WILL|CAN|OUGHT TO)\s+(BE\s+)?(KEEP|RETAIN|ALLOW|STAY)',
            r'(BEEN|WAS|IS)\s+(KEEP|RETAIN|ALLOW)',
            r'(KEEP|RETAIN|ALLOW)\s+(IT|THIS|THAT)',
            r'\b(LET\s+IT\s+STAY|LEAVE\s+IT|CAN\s+STAY)\b',
            r'\b(NO\s+NEED\s+TO\s+REMOV|DOES\s+NOT\s+NEED\s+REMOV)\b'
        ]
        
        # Check for REMOVE patterns first (more conservative approach)
        for pattern in modal_remove_patterns:
            if re.search(pattern, text):
                return 'REMOVE'
        
        for pattern in modal_keep_patterns:
            if re.search(pattern, text):
                return 'KEEP'
        
        # If no decision found, return None
        return None

class RedditModerator:
    """Main Reddit moderator bot class."""
    
    def __init__(self, gui_queue=None):
        self.config = self.load_config()
        self.logger = ModerationLogger(self.config, gui_queue)
        self.timestamp_manager = TimestampManager(self.config)
        self.adaptive_delay_manager = AdaptiveDelayManager(self.config)
        self.rate_limiter = RateLimiter(self.config, self.logger)
        self.llm_analyzer = LLMAnalyzer(self.config, self.logger)
        self.reddit = None
        self.subreddit = None
        
        # GUI integration
        self.gui_queue = gui_queue
        
        # Thread control
        self.running = False
        self.paused = False
        self.stop_requested = False
        
        # Moderator whitelist - accounts to skip analysis
        moderator_username = os.getenv('MODERATOR_USERNAME', 'your-mod-team')
        self.mod_whitelist = {
            moderator_username,
            'AutoModerator',
            # Add other official mod accounts here
        }
        
        # Comment tracking
        self.removed_comments = []  # In-memory list of removed comments
        self.removed_count = 0      # Counter for removed comments
        # Comment tracking initialization complete
        
        # Statistics tracking
        self.comments_analyzed = 0
        self.comments_removed = 0
        self.logger.load_statistics()  # Load existing statistics
    
    def load_config(self) -> BotConfig:
        """Load configuration from environment variables."""
        return BotConfig()
    
    def initialize_reddit(self):
        """Initialize Reddit API connection."""
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.reddit_client_id,
                client_secret=self.config.reddit_client_secret,
                username=self.config.reddit_username,
                password=self.config.reddit_password,
                user_agent=self.config.reddit_user_agent
            )
            
            # Test connection
            self.reddit.user.me()
            self.subreddit = self.reddit.subreddit(self.config.subreddit_name)
            
            # Update the logger with the subreddit reference
            self.logger.subreddit = self.subreddit
            
            # Reinitialize logger with reddit instance for wiki functionality
            if self.config.wiki_transparency_enabled:
                try:
                    # Create new logger instance with reddit instance
                    self.logger = ModerationLogger(self.config, self.gui_queue, self.subreddit, self.reddit)
                    print(f"{self.logger.GREY}WikiTransparencyManager initialized with Reddit connection{self.logger.RESET}")
                except Exception as e:
                    print(f"{self.logger.GREY}Warning: Failed to initialize WikiTransparencyManager: {e}{self.logger.RESET}")
            
            print(f"{self.logger.GREY}Successfully connected to Reddit as u/{self.config.reddit_username}{self.logger.RESET}")
            return True
            
        except Exception as e:
            self.logger.log_error("Reddit Connection", str(e))
            return False
    
    def start(self):
        """Start the bot."""
        if self.running:
            return False
        
        self.running = True
        self.paused = False
        self.stop_requested = False
        
        self.send_gui_message("log", "Starting Reddit Moderator Bot...")
        self.logger.log_startup()
        
        if not self.initialize_reddit():
            self.logger.log_error("Startup", "Failed to initialize Reddit connection")
            self.send_gui_message("log", "❌ Failed to initialize Reddit connection")
            self.running = False
            return False
        
        self.send_gui_message("log", "✅ Bot started successfully. Monitoring for comments...")
        return True
    
    def stop(self):
        """Stop the bot."""
        self.stop_requested = True
        self.running = False
        self.paused = False
        self.send_gui_message("log", "🛑 Bot stopped")
    
    def pause(self):
        """Pause the bot."""
        if self.running:
            self.paused = True
            self.send_gui_message("log", "⏸️ Bot paused")
    
    def resume(self):
        """Resume the bot."""
        if self.running and self.paused:
            self.paused = False
            self.send_gui_message("log", "▶️ Bot resumed")
    
    def is_running(self):
        """Check if bot is running."""
        return self.running
    
    def is_paused(self):
        """Check if bot is paused."""
        return self.paused
    
    def run(self):
        """Main bot execution loop for threading."""
        # Don't call start() here - it should already be called by the worker thread
        if not self.running:
            self.send_gui_message("log", "❌ Bot is not running - cannot start execution loop")
            return
        
        try:
            while self.running and not self.stop_requested:
                # Handle pause state
                if self.paused:
                    time.sleep(1)  # Check every second while paused
                    continue
                
                self.check_comments()
                
                # Check for stop request before sleeping
                if self.stop_requested:
                    break
                
                current_delay = self.adaptive_delay_manager.get_current_delay()
                delay_info = self.adaptive_delay_manager.get_status_info()
                
                # Log adaptive delay information
                if delay_info['is_at_base']:
                    self.send_gui_message("log", f"Next check in {current_delay:.1f}s (base interval)")
                else:
                    self.send_gui_message("log", f"Next check in {current_delay:.1f}s (adaptive - {delay_info['consecutive_empty_checks']} empty checks)")
                
                # Sleep in small increments to allow for responsive stop/pause
                sleep_time = current_delay
                while sleep_time > 0 and self.running and not self.stop_requested:
                    if self.paused:
                        break
                    time.sleep(min(1, sleep_time))  # Sleep max 1 second at a time
                    sleep_time -= 1
                
        except Exception as e:
            self.logger.log_error("Runtime", str(e))
            self.send_gui_message("log", f"❌ Runtime error: {str(e)}")
        finally:
            self.running = False
            self.send_gui_message("log", "Bot execution finished")
    
    
    def update_safe_mode(self, safe_mode: bool):
        """Update safe mode setting."""
        self.config.safe_mode = safe_mode
        mode_text = "ON" if safe_mode else "OFF"
        self.send_gui_message("log", f"🛡️ Safe Mode: {mode_text}")
    
    def update_llm_provider(self, provider: str):
        """Update LLM provider setting."""
        if provider.lower() in ['ollama', 'gemini', 'deepseek']:
            self.config.llm_provider = provider.lower()
            try:
                # Reinitialize LLM analyzer with new provider
                self.llm_analyzer = LLMAnalyzer(self.config, self.logger)
                self.send_gui_message("log", f"🔄 LLM provider changed to: {provider.upper()}")
            except Exception as e:
                self.logger.log_error("LLM Provider", f"Failed to switch to {provider}: {str(e)}")
                self.send_gui_message("log", f"❌ Failed to switch to {provider}: {str(e)}")

    def update_ollama_model(self, model: str):
        """Update the Ollama model at runtime and reinitialize analyzer if needed."""
        try:
            previous = getattr(self.config, 'ollama_model', None)
            self.config.ollama_model = model
            self.send_gui_message("log", f"🧩 Ollama model set to: {model}")

            # If we're currently using Ollama, reinitialize the provider/analyzer
            if getattr(self.config, 'llm_provider', '').lower() == 'ollama':
                try:
                    self.llm_analyzer = LLMAnalyzer(self.config, self.logger)
                    # Optional health check to verify the model is available
                    try:
                        healthy = getattr(self.llm_analyzer, 'provider', None).check_health()
                    except Exception:
                        healthy = False
                    if healthy:
                        self.send_gui_message("log", f"✅ Ollama model '{model}' is available and ready")
                    else:
                        self.send_gui_message("log", f"⚠️ Ollama model '{model}' might not be available. Ensure it is pulled in Ollama.")
                except Exception as e:
                    self.logger.log_error("Ollama Model", f"Failed to activate Ollama model '{model}': {str(e)}")
                    self.send_gui_message("log", f"❌ Failed to activate Ollama model: {str(e)}")
            else:
                # Not currently using Ollama, just record the change
                pass
        except Exception as e:
            self.logger.log_error("Ollama Model", f"Failed to set Ollama model to '{model}': {str(e)}")
            self.send_gui_message("log", f"❌ Failed to set Ollama model: {str(e)}")

    def manual_wiki_update(self):
        """Manually trigger a wiki update."""
        if not self.logger.wiki_manager:
            self.send_gui_message("log", "❌ Wiki transparency is not enabled")
            return False
        
        try:
            success = self.logger.wiki_manager.update_wiki()
            if success:
                status = self.logger.wiki_manager.get_status()
                self.send_gui_message("log", f"✅ Wiki updated successfully. Total entries: {status['total_entries']}")
                return True
            else:
                self.send_gui_message("log", "❌ Wiki update failed")
                return False
        except Exception as e:
            self.logger.log_error("Manual Wiki Update", str(e))
            self.send_gui_message("log", f"❌ Wiki update error: {str(e)}")
            return False
    
    def get_wiki_status(self):
        """Get current wiki transparency status."""
        if not self.logger.wiki_manager:
            return {"enabled": False, "message": "Wiki transparency is not enabled"}
        
        try:
            status = self.logger.wiki_manager.get_status()
            status["enabled"] = True
            return status
        except Exception as e:
            return {"enabled": True, "error": str(e)}
    
    def clear_wiki_data(self):
        """Clear all wiki data (for testing/reset purposes)."""
        if not self.logger.wiki_manager:
            self.send_gui_message("log", "❌ Wiki transparency is not enabled")
            return False
        
        try:
            self.logger.wiki_manager.clear_data()
            self.send_gui_message("log", "✅ Wiki data cleared successfully")
            return True
        except Exception as e:
            self.logger.log_error("Clear Wiki Data", str(e))
            self.send_gui_message("log", f"❌ Error clearing wiki data: {str(e)}")
            return False
    
    def send_gui_message(self, msg_type: str, text: str, **kwargs):
        """Send a message to the GUI queue if available."""
        if self.gui_queue:
            message = {'type': msg_type, 'text': text, **kwargs}
            try:
                self.gui_queue.put_nowait(message)
            except:
                pass  # Queue might be full, ignore
    
    def check_comments(self):
        """Check for new comments and analyze them with enhanced error handling for 500 errors."""
        try:
            last_check = self.timestamp_manager.get_last_check_time()
            current_time = datetime.now(timezone.utc)
            
            # Get comments since last check (or last 100 if first run)
            if last_check:
                print(f"{self.logger.GREY}Checking comments since {last_check}{self.logger.RESET}")
                comments = list(self.subreddit.comments(limit=None))
                # Filter comments newer than last check
                new_comments = [
                    comment for comment in comments 
                    if datetime.fromtimestamp(comment.created_utc, timezone.utc) > last_check
                ]
            else:
                print(f"{self.logger.GREY}First run - checking last 100 comments{self.logger.RESET}")
                new_comments = list(self.subreddit.comments(limit=100))
            
            # Handle adaptive delay based on comment activity
            if len(new_comments) > 0:
                # Reset delay when new comments are found
                self.adaptive_delay_manager.reset_delay()
                print(f"{self.logger.GREY}Found {len(new_comments)} new comments to analyze{self.logger.RESET}")
                
                for comment in new_comments:
                    # Check for stop request before processing each comment
                    if self.stop_requested:
                        print(f"{self.logger.GREY}Stop requested - aborting comment processing{self.logger.RESET}")
                        break
                    self.rate_limiter.wait_if_needed()
                    self.analyze_and_moderate_comment(comment)
            else:
                # Increase delay when no new comments are found
                self.adaptive_delay_manager.increase_delay()
                # Only log "Found 0 new comments" when at base interval to reduce noise
                if self.adaptive_delay_manager.is_at_base_interval():
                    print(f"{self.logger.GREY}Found 0 new comments{self.logger.RESET}")
            
            # Update last check timestamp
            self.timestamp_manager.update_last_check_time(current_time)
            
        except Exception as e:
            error_message = str(e)
            
            # Check if this is a 500 error from Reddit API
            if "500" in error_message or "Internal Server Error" in error_message:
                # Handle 500 errors with enhanced visibility and retry logic
                self._handle_500_error(error_message)
            else:
                # Log other errors normally
                self.logger.log_error("Comment Check", error_message)
    
    def _handle_500_error(self, error_message: str, max_retries: int = None):
        """Handle 500 errors with enhanced visibility and progressive retry logic."""
        # Track retry attempts for this specific error
        if not hasattr(self, '_500_retry_attempts'):
            self._500_retry_attempts = 0
        
        # Calculate retry delay: start with 5 seconds, increase by 3 seconds each attempt
        base_delay = 5.0
        delay_increment = 3.0
        retry_delay = base_delay + (self._500_retry_attempts * delay_increment)
        
        # Log the 500 error with enhanced visibility
        self.logger.log_api_error(
            "REDDIT API 500 ERROR", 
            error_message, 
            retry_delay=retry_delay,
            attempt=self._500_retry_attempts + 1
        )
        
        # Increment retry counter
        self._500_retry_attempts += 1
        
        # Sleep for the calculated delay before retrying
        print(f"{self.logger.GREY}⏱️  Waiting {retry_delay:.1f}s before retrying API call...{self.logger.RESET}")
        time.sleep(retry_delay)
        
        # Reset retry counter if we've been successful for a while (prevent infinite growth)
        if self._500_retry_attempts > 10:
            self._500_retry_attempts = 5  # Reset to a moderate level
    
    def analyze_and_moderate_comment(self, comment):
        """Analyze a single comment and take moderation action if needed."""
        try:
            # Skip deleted/removed comments
            if comment.body in ['[deleted]', '[removed]']:
                return
            
            # Skip bot's own comments
            if comment.author and comment.author.name == self.config.reddit_username:
                return
            
            author_name = comment.author.name if comment.author else '[deleted]'
            
            # Skip moderator whitelist accounts
            if comment.author and author_name in self.mod_whitelist:
                print(f"{self.logger.GREY}Skipping whitelisted moderator account: u/{author_name}{self.logger.RESET}")
                return
            comment_text = comment.body
            
            print(f"{self.logger.GREY}Analyzing comment {comment.id} by{self.logger.RESET} u/{author_name}")
            
            # Check for stop request before starting LLM analysis
            if self.stop_requested:
                print(f"{self.logger.GREY}Stop requested - skipping comment analysis{self.logger.RESET}")
                return
            
            # Analyze with LLM
            decision = self.llm_analyzer.analyze_comment(comment_text)
            
            # Get the comment permalink for GUI click functionality
            permalink = f"https://reddit.com{comment.permalink}"
            
            if decision == 'REMOVE':
                if self.config.safe_mode:
                    # Safe mode: log what would happen but don't actually remove
                    self.logger.log_comment_analysis(
                        comment.id, author_name, "WOULD REMOVE", "- violates community rules [SAFE MODE]", comment_text, permalink
                    )
                    self.logger.log_moderation_action(
                        comment.id, author_name, "WOULD REMOVE (SAFE MODE)"
                    )
                else:
                    # Live mode: actually remove the comment
                    self.logger.log_comment_analysis(
                        comment.id, author_name, "REMOVE", "- violates community rules", comment_text, permalink
                    )
                    
                    try:
                        comment.mod.remove()
                        self.logger.log_moderation_action(
                            comment.id, author_name, "REMOVED"
                        )
                        # Add to removed comments tracking
                        self.logger.add_removed_comment(comment_text, comment.id, permalink, "violates community rules")
                    except Exception as e:
                        self.logger.log_error(
                            "Moderation Action", 
                            f"Failed to remove comment {comment.id}: {str(e)}"
                        )
                    
            elif decision == 'KEEP':
                self.logger.log_comment_analysis(
                    comment.id, author_name, "KEEP", "- does not violate rules", comment_text, permalink
                )
                # Statistics are updated via LLM token usage logging
                self.logger.save_statistics()
            else:
                # LLM analysis failed
                self.logger.log_comment_analysis(
                    comment.id, author_name, "SKIPPED", "- LLM analysis failed", comment_text, permalink
                )
                # For failed LLM analysis, manually send comment_analyzed message
                self.logger.send_gui_message("comment_analyzed", "Comment processed")
                # Statistics are updated via LLM token usage logging
                self.logger.save_statistics()
                
        except Exception as e:
            self.logger.log_error("Comment Analysis", f"Error processing comment {comment.id}: {str(e)}")
        
        # Print divider to separate different comment analyses
        print(f"{self.logger.GREY}{self.logger.DIVIDER}{self.logger.RESET}")
    
    # Wiki functionality has been removed

    def _test_reddit_connectivity(self):
        """Test Reddit API connectivity with comprehensive diagnostics."""
        connectivity_result = {
            'status': 'UNKNOWN',
            'details': {
                'network_test': False,
                'auth_test': False,
                'permissions_test': False,
                'wiki_test': False
            },
            'errors': []
        }
        
        try:
            # Test 1: Basic network connectivity
            print("Testing basic Reddit API network connectivity")
            try:
                # Simple API call to test connectivity
                user = self.reddit.user.me()
                connectivity_result['details']['network_test'] = True
                print(f"Network connectivity test passed - authenticated as {user.name}")
            except Exception as network_error:
                connectivity_result['errors'].append(f"Network test failed: {network_error}")
                print(f"Network connectivity test failed: {network_error}")
                return connectivity_result
            
            # Test 2: Authentication verification
            print("Verifying Reddit authentication")
            try:
                # Verify we can access user info
                user_info = {
                    'username': user.name,
                    'has_verified_email': getattr(user, 'has_verified_email', None),
                    'is_suspended': getattr(user, 'is_suspended', None)
                }
                connectivity_result['details']['auth_test'] = True
                print(f"Authentication verification passed for user: {user_info['username']}")
            except Exception as auth_error:
                connectivity_result['errors'].append(f"Authentication test failed: {auth_error}")
                print(f"Authentication verification failed: {auth_error}")
                return connectivity_result
            
            # Test 3: Subreddit access and permissions
            print(f"Testing subreddit access for r/{self.config.subreddit_name}")
            try:
                subreddit = self.reddit.subreddit(self.config.subreddit_name)
                
                # Test basic subreddit access
                subreddit_info = {
                    'display_name': subreddit.display_name,
                    'subscribers': getattr(subreddit, 'subscribers', 'N/A'),
                    'public_description': getattr(subreddit, 'public_description', 'N/A')[:100]
                }
                
                # Test moderator permissions
                try:
                    me = subreddit.me()
                    if me:
                        mod_perms = list(getattr(me, 'mod_permissions', []))
                        connectivity_result['details']['permissions_test'] = True
                        print(f"Subreddit permissions verified: {mod_perms}")
                    else:
                        connectivity_result['errors'].append("Bot is not a moderator of the subreddit")
                        print("Bot is not a moderator of the subreddit")
                        return connectivity_result
                except Exception as perm_error:
                    connectivity_result['errors'].append(f"Permission check failed: {perm_error}")
                    print(f"Permission check failed: {perm_error}")
                    return connectivity_result
                    
            except Exception as subreddit_error:
                connectivity_result['errors'].append(f"Subreddit access failed: {subreddit_error}")
                print(f"Subreddit access failed: {subreddit_error}")
                return connectivity_result
            
            # Test 4: Wiki-specific access - Wiki functionality has been removed
            print("Wiki functionality has been removed - skipping wiki access test")
            connectivity_result['details']['wiki_test'] = False
            
            # Test 5: Rate limiting check
            print("Checking rate limiting status")
            try:
                # Check if we're being rate limited
                rate_limit_info = {
                    'remaining_requests': getattr(self.reddit, 'auth', {}).get('limits', {}).get('remaining', 'Unknown'),
                    'reset_timestamp': getattr(self.reddit, 'auth', {}).get('limits', {}).get('reset_timestamp', 'Unknown')
                }
                print(f"Rate limiting check completed: {rate_limit_info}")
            except Exception as rate_error:
                print(f"Could not check rate limiting: {rate_error}")
            
            # All tests passed
            connectivity_result['status'] = 'PASS'
            print("All Reddit connectivity tests passed")
            
        except Exception as overall_error:
            connectivity_result['status'] = 'FAIL'
            connectivity_result['errors'].append(f"Overall connectivity test failed: {overall_error}")
            print(f"Overall connectivity test failed: {overall_error}")
        
        return connectivity_result

    # Wiki functionality has been removed

def main():
    """Main function to run the Reddit moderator bot."""
    try:
        config = BotConfig()
        
        # Display startup configuration
        grey = '\033[93m'  # Light yellow for technical information
        reset = '\033[0m'
        print(f"{grey}\n=== Reddit Moderator Bot Configuration ==={reset}")
        print(f"{grey}LLM Provider: {config.llm_provider}{reset}")
        if config.llm_provider == 'ollama':
            print(f"{grey}Model: {config.ollama_model}{reset}")
            print(f"{grey}Ollama URL: {config.ollama_url}{reset}")
        elif config.llm_provider == 'gemini':
            print(f"{grey}Model: {config.gemini_model}{reset}")
        print(f"{grey}LLM Timeout: {config.llm_timeout} seconds{reset}")
        print(f"{grey}Subreddit: r/{config.subreddit_name}{reset}")
        if config.safe_mode:
            print(f"{grey}🛡️  Mode: SAFE MODE (no actual removals){reset}")
        else:
            print(f"{grey}⚠️  Mode: LIVE MODE (will remove flagged comments){reset}")
        print(f"{grey}Processing: Live comments only{reset}")
        print(f"{grey}=========================================={reset}\n")
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        return
    
    try:
        bot = RedditModerator()
        if bot.start():
            bot.run()
        else:
            print("❌ Failed to start the bot")
            sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
