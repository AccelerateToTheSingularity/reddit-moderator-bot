# Reddit Moderator Bot - Complete Setup Guide

## Overview

This Reddit Moderator Bot uses AI/LLM analysis to automatically moderate comments in your subreddit based on configurable rules. It supports multiple LLM providers and provides comprehensive logging for transparency.

## Prerequisites

### Required Accounts & Permissions
1. **Reddit Account** with moderator permissions on your target subreddit
2. **Reddit App Registration** - Create at https://www.reddit.com/prefs/apps
3. **LLM Provider** (choose one):
   - **Ollama** (recommended for privacy) - Local AI models
   - **Google Gemini** - Cloud AI service
   - **DeepSeek** - Cloud AI service

### Required Software
1. **Python 3.8+** - Download from https://python.org
2. **Git** (optional) - For cloning the repository

## Step-by-Step Setup

### 1. Download the Bot

#### Option A: Download ZIP
1. Download this repository as a ZIP file
2. Extract to your desired location

#### Option B: Clone with Git
```bash
git clone <repository-url>
cd reddit-moderator-bot
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install praw requests python-dotenv
```

### 3. Reddit API Setup

#### Create Reddit App
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in:
   - **Name**: `Your Bot Name`
   - **App type**: `script`
   - **Description**: `Moderation bot for r/yoursubreddit`
   - **About URL**: Leave blank
   - **Redirect URI**: `http://localhost:8080`
4. Click "Create app"
5. Note down:
   - **Client ID** (under the app name)
   - **Client Secret** (shown after creation)

#### Create Bot Account (Optional but Recommended)
1. Create a new Reddit account for your bot
2. Add this account as a moderator to your subreddit
3. Give it appropriate permissions (Posts, Comments)

### 4. LLM Provider Setup

#### Option A: Ollama (Recommended - Local & Private)
1. Install Ollama from https://ollama.ai
2. Install a model:
   ```bash
   ollama pull llama3.2
   # or
   ollama pull gemma2
   ```
3. Start Ollama:
   ```bash
   ollama serve
   ```

#### Option B: Google Gemini
1. Go to https://makersuite.google.com/app/apikey
2. Create an API key
3. Note the key for configuration

#### Option C: DeepSeek
1. Go to https://platform.deepseek.com
2. Create an account and get an API key
3. Note the key for configuration

### 5. Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual values:

```env
# Reddit API Configuration
REDDIT_CLIENT_ID=your_reddit_app_client_id
REDDIT_CLIENT_SECRET=your_reddit_app_client_secret
REDDIT_USERNAME=your_bot_account_username
REDDIT_PASSWORD=your_bot_account_password
REDDIT_USER_AGENT=YourBot/1.0 by YourUsername

# Target Subreddit (without r/)
SUBREDDIT_TO_MONITOR=your_subreddit_name

# LLM Provider (ollama, gemini, or deepseek)
LLM_PROVIDER=ollama

# Ollama Configuration (if using Ollama)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Gemini Configuration (if using Gemini)
GEMINI_API_KEY=your_gemini_api_key_here

# DeepSeek Configuration (if using DeepSeek)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Bot Settings
MODERATOR_USERNAME=your_moderator_username
CHECK_INTERVAL_SECONDS=30
```

### 6. Customize Moderation Rules

Edit `prompts.py` to customize the moderation criteria for your subreddit:

1. Modify the `get_moderation_prompt()` function
2. Update the classification rules
3. Set specific criteria for your community

### 7. Test the Bot

#### Test LLM Connection
```bash
python test_deepseek_integration.py  # or appropriate test file
```

#### Test Reddit Connection
```bash
python test_bot_integration.py
```

### 8. Run the Bot

#### Foreground (for testing)
```bash
python moderator_bot.py
```

#### Background/Service
- **Windows**: Use Task Scheduler or run as a service
- **Linux/Mac**: Use systemd, cron, or screen/tmux

## Security Best Practices

### 🔒 Protect Your Credentials
1. **Never commit `.env` to version control**
2. **Use environment variables** in production
3. **Regularly rotate** API keys
4. **Use dedicated bot accounts** with minimal permissions

### 🛡️ Bot Permissions
1. **Principle of least privilege** - Only give necessary permissions
2. **Monitor bot actions** through logs
3. **Set up alerts** for unusual activity

### 🔍 Monitoring
1. **Check logs regularly** in `logs/moderation.log`
2. **Monitor Reddit's rate limits**
3. **Review moderation decisions** periodically

## Configuration Options

### LLM Providers Comparison

| Provider | Pros | Cons | Cost |
|----------|------|------|------|
| **Ollama** | Private, No API costs, Offline | Requires local hardware | Free |
| **Gemini** | Fast, Reliable, Good accuracy | Requires internet, API costs | Pay per use |
| **DeepSeek** | Cost-effective, Good performance | Requires internet, API costs | Pay per use |

### Recommended Settings

#### For High-Traffic Subreddits
```env
CHECK_INTERVAL_SECONDS=10
MAX_COMMENTS_PER_CHECK=20
RATE_LIMIT_ENABLED=true
```

#### For Low-Traffic Subreddits
```env
CHECK_INTERVAL_SECONDS=60
MAX_COMMENTS_PER_CHECK=10
RATE_LIMIT_ENABLED=false
```

## Troubleshooting

### Common Issues

#### "Cannot connect to Ollama"
- Ensure Ollama is running: `ollama serve`
- Check if model is available: `ollama list`
- Verify URL in `.env` file

#### "Reddit API Authentication Failed"
- Check client ID and secret in `.env`
- Verify username and password
- Ensure bot account exists

#### "Permission Denied"
- Verify bot account has moderator permissions
- Check Reddit app configuration
- Ensure correct subreddit name in `.env`

#### "Rate Limited"
- Increase `CHECK_INTERVAL_SECONDS`
- Reduce `MAX_COMMENTS_PER_CHECK`
- Enable `RATE_LIMIT_ENABLED=true`

### Getting Help

1. **Check logs** in `logs/moderation.log`
2. **Verify configuration** in `.env`
3. **Test components** individually using test scripts

## Legal & Ethical Considerations

### Reddit Terms of Service
- **Follow Reddit's API terms**
- **Respect rate limits**
- **Don't circumvent Reddit features**

### Moderation Ethics
- **Be transparent** with your community
- **Document moderation criteria**
- **Provide appeals process**
- **Regularly review** bot decisions

### Privacy
- **Minimize data collection**
- **Secure API keys and credentials**
- **Consider user privacy** in logging

## Advanced Usage

### Custom Prompts
Modify `prompts.py` to:
- Add specific rule detection
- Implement warning systems
- Create custom response templates

### Integration
- **Discord notifications** for moderation actions
- **Database logging** for analytics
- **Web dashboard** for monitoring

### Scaling
- **Multiple subreddits** support
- **Load balancing** for high traffic
- **Backup moderation** systems

## Support

For issues and questions:
1. Check this setup guide
2. Review the troubleshooting section
3. Check existing GitHub issues
4. Create a new issue with detailed information

---

**⚠️ Important**: Always test thoroughly in a development environment before deploying to production. Monitor the bot closely during initial deployment to ensure it behaves as expected.