# Reddit Moderator Bot with LLM Analysis

A lean, automated moderation bot that uses local LLM analysis to detect and moderate comments based on configurable rules and criteria.

## Features

- **Real-time monitoring**: Checks for new comments on configurable intervals
- **Local LLM analysis**: Uses local models via Ollama for comment classification
- **Multiple LLM providers**: Supports Ollama, Gemini, and DeepSeek
- **Audit logging**: Comprehensive logging for all moderation actions
- **Timestamp tracking**: Analyzes all comments since last run (handles intermittent operation)
- **Conservative rate limiting**: Respects Reddit API limits
- **Error handling**: Graceful handling of LLM unavailability with retries and backoff
- **Configurable prompts**: Customizable moderation criteria and decision making

## Prerequisites

1. **Python 3.8+**
2. **Ollama** with your preferred model (recommended for privacy)
3. **Reddit API credentials**
4. **Reddit account with moderator permissions** on target subreddit

## Setup Instructions

### 1. Install and Start Ollama

```bash
# Download and install Ollama from https://ollama.ai
# Then pull the required model:
ollama pull llama3.2:3b

# Start Ollama server:
ollama serve
```

### 2. Verify Installation

Run the test script to verify everything is working:

```bash
python test_llm.py
```

This will:
- Check Ollama connection
- Test LLM analysis on example comments
- Validate positive comment classification

### 3. Run the Bot

```bash
python moderator_bot.py
```

## Configuration

The bot is configured via environment variables in the `.env` file:

- `REDDIT_CLIENT_ID`: Your Reddit app client ID
- `REDDIT_CLIENT_SECRET`: Your Reddit app secret
- `REDDIT_USERNAME`: Bot account username
- `REDDIT_PASSWORD`: Bot account password
- `REDDIT_USER_AGENT`: Bot description
- `SUBREDDIT_TO_MONITOR`: Target subreddit name (without r/)
- `LLM_PROVIDER`: Choose between 'ollama', 'gemini', or 'deepseek'
- `MODERATOR_USERNAME`: Your moderator account username

## How It Works

1. **Comment Monitoring**: Configurable interval checking for new comments since the last run
2. **LLM Analysis**: Each comment is analyzed using your chosen LLM with customizable prompts
3. **Binary Classification**: The LLM responds with either "REMOVE" or "KEEP"
4. **Moderation Action**: Comments classified as "REMOVE" are removed with optional logging
5. **Audit Logging**: All actions are logged for transparency and review

## Customizable Moderation

The bot can be configured to detect comments that violate your subreddit's specific rules by:
- Modifying the prompts in `prompts.py`
- Adjusting the classification criteria
- Setting custom moderation policies
- Configuring automated responses
- Defining rule violations specific to your community
- Setting boundaries for acceptable discourse

## File Structure

```
├── moderator_bot.py          # Main bot application
├── test_llm.py               # LLM testing script
├── .env                      # Configuration (credentials)
├── credentials.txt           # Original credentials file
├── comment_examples.txt          # Training examples
├── logs/                     # Audit logs directory
│   └── moderation.log        # Moderation action logs
└── data/                     # Bot data directory
    └── last_check.json       # Last check timestamp
```

## Logging

All bot activities are logged to both console and `logs/moderation.log`:

- **INFO**: General bot operations, comment analysis results
- **WARNING**: Moderation actions (comment removals)
- **ERROR**: Connection issues, API errors, LLM failures

## Rate Limiting

The bot implements conservative rate limiting:
- Maximum 60 requests per minute
- Maximum 3600 requests per hour
- Automatic backoff when approaching limits

## Error Handling

- **LLM Unavailable**: Retries with exponential backoff, skips comments if all retries fail
- **Reddit API Errors**: Logged but don't stop the bot
- **Network Issues**: Automatic retry with backoff

## Testing

The `test_llm.py` script validates:
1. Ollama connection and model availability
2. LLM analysis on provided comment examples
3. Positive comment classification (should be KEEP)

## Troubleshooting

### "Cannot connect to Ollama"
- Ensure Ollama is installed and running: `ollama serve`
- Verify the model is available: `ollama list`
- Pull the model if needed: `ollama pull llama3.2` (or your preferred model)

### "Reddit API Authentication Failed"
- Verify credentials in `.env` file
- Check Reddit app configuration at https://www.reddit.com/prefs/apps
- Ensure bot account exists and credentials are correct

### "Permission denied for moderation actions"
- Verify bot account has moderator permissions on your target subreddit
- Check Reddit app permissions and scope

## Customization

To adjust detection sensitivity, modify the system prompt in the `LLMAnalyzer._create_system_prompt()` method in `moderator_bot.py`.

## Safety Features

- **Conservative approach**: Only removes comments with clear REMOVE classification
- **Comprehensive logging**: Full audit trail of all actions
- **Rate limiting**: Respects Reddit API guidelines
- **Error recovery**: Continues operation despite temporary failures
