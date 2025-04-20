# Ipril - Grammar Assistant Bot

[![Tests](https://github.com/imansprn/ipril/actions/workflows/bot.yml/badge.svg)](https://github.com/imansprn/ipril/actions/workflows/bot.yml)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Telegram bot that helps users improve their writing in multiple languages using AI-powered grammar correction.

## Features

- Grammar correction in 6 languages (English, Spanish, French, German, Italian, Russian)
- User language preference persistence
- Rate limiting (15 requests/minute per user)
- Automated daily backups
- Error handling and logging
- Unit tests for core functionality

## Commands

- `/start` - Welcome message with instructions
- `/setlang [code]` - Change language preference
- `/currentlang` - Show current language

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` with your:
   - Telegram Bot Token (from @BotFather)
   - DeepSeek API Key

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Run the bot:
   ```bash
   python main.py
   ```

3. Run tests:
   ```bash
   pytest tests/ -v
   ```

## Deployment with GitHub Actions

The bot can be deployed for free using GitHub Actions (for public repositories):

1. Go to your repository's Settings > Secrets and variables > Actions
2. Add the following secrets:
   - `BOT_TOKEN`: Your Telegram bot token
   - `DEEPSEEK_API_KEY`: Your DeepSeek API key
3. The workflow will automatically run on:
   - Push to main branch
   - Manual trigger (workflow_dispatch)

The bot will run continuously on GitHub's servers. You can monitor its status in the Actions tab.

## Testing

The project includes unit tests for core functionality:
- User data management
- Rate limiting
- Bot initialization
- Data persistence

Run tests locally:
```bash
pytest tests/ -v
```

## File Structure

- `main.py` - Main bot implementation
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (not in git)
- `user_data.json` - User preferences storage
- `backups/` - Daily backups of user data
- `bot.log` - Application logs
- `tests/` - Unit tests

## Error Handling

The bot includes comprehensive error handling for:
- API failures
- Invalid inputs
- Rate limit exceeded
- File system operations

All errors are logged to `bot.log` for debugging.

## License

MIT License 