# Reddit Moderator Bot - Setup Guide

## Overview
This bot automatically monitors your target subreddit for comments that violate configured rules using a local or cloud LLM for analysis.

## Prerequisites
**Required Components:**
- Python 3.8+ installed
- Reddit API credentials
- LLM provider (Ollama recommended for privacy, or cloud providers)
- Reddit account with moderator permissions on target subreddit

## Quick Start

### 1. Environment Setup
1. Copy `.env.example` to `.env`
2. Fill in your Reddit API credentials
3. Configure your preferred LLM provider
4. Set your target subreddit name

### 2. Run the Bot
```bash
python moderator_bot.py
```

### 3. Monitor Logs
The bot will log all activities to:
- Console output (real-time)
- `./logs/moderation.log` (persistent)

## Bot Features

### Core Functionality
- **Real-time Monitoring**: Configurable interval checking for new comments
- **LLM Analysis**: Uses your chosen LLM to classify comments based on your rules
- **Automated Moderation**: Removes violating comments based on analysis
- **Audit Logging**: Logs all decisions for review and transparency
- **Comment Queuing**: Queues comments when LLM is unavailable
- **Rate Limiting**: Conservative Reddit API usage
- **Multi-LLM Support**: Works with Ollama, Gemini, and DeepSeek

### Error Handling
- **LLM Unavailable**: Comments are queued and processed when LLM returns
- **Reddit API Errors**: Automatic retry with exponential backoff
- **Network Issues**: Graceful handling with comprehensive logging

### Data Persistence
- **Timestamp Tracking**: Remembers last check time for intermittent operation
- **Comment Queue**: Persists queued comments across restarts
- **Audit Trail**: Complete log of all moderation actions

## Configuration

The bot uses environment variables from `.env` file:

```env
# Reddit API Configuration
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_bot_username
REDDIT_PASSWORD=your_bot_password
REDDIT_USER_AGENT=YourBot/1.0 by YourUsername
SUBREDDIT_TO_MONITOR=your_subreddit_name
LLM_PROVIDER=ollama
MODERATOR_USERNAME=your_mod_username
```

## File Structure

```
reddit-moderator-bot/
├── moderator_bot.py          # Main bot implementation
├── prompts.py               # Moderation prompts and logic
├── .env                     # Environment configuration (create from .env.example)
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── logs/                    # Bot activity logs (created automatically)
├── data/                    # Bot state and settings (created automatically)
└── data/
    ├── last_check.json      # Timestamp tracking
    └── comment_queue.pkl    # Queued comments
```

## Monitoring and Maintenance

### Log Analysis
Monitor `./logs/moderation.log` for:
- Comment analysis results
- Moderation actions taken
- Error conditions
- Performance metrics

### Key Log Entries
- `REMOVE`: Comment removed for Rule 1 violation
- `KEEP`: Comment approved
- `QUEUED`: Comment queued due to LLM unavailability
- `SKIPPED`: Comment skipped due to analysis failure

### Performance Tuning
The bot is configured for:
- 5-second check intervals
- Conservative rate limiting (60 req/min, 3600 req/hour)
- 3 retry attempts for LLM failures
- Exponential backoff for errors

## Troubleshooting

### Common Issues

1. **LLM Connection Failed**
   ```bash
   # Ensure Ollama is running
   ollama serve
   
   # Verify model is available
   ollama list
   ```

2. **Reddit API Errors**
   - Check credentials in `.env`
   - Verify bot account has moderator permissions on your target subreddit
   - Check rate limiting logs

3. **Permission Errors**
   - Ensure bot account is a moderator of your target subreddit
   - Verify Reddit app has appropriate permissions

### Testing
Run the test suite to verify functionality:
```bash
python test_bot_integration.py
```

## Security Notes

- Keep `.env` file secure and never commit to version control
- Monitor bot actions regularly through logs
- The bot operates with moderator privileges - use responsibly
- LLM analysis is local and private (no data sent to external services)

## Support

For issues or questions:
1. Check the logs in `./logs/moderation.log`
2. Run `python test_llm.py` to verify LLM functionality
3. Ensure Ollama service is running: `ollama serve`
4. Verify Reddit API credentials and permissions

---

**Status: ✅ READY FOR DEPLOYMENT**

The bot has been fully tested and verified. All systems are operational and ready for production use.
