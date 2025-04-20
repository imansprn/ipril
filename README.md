# Ipril - Grammar Assistant Bot

A Telegram bot that helps users improve their writing in multiple languages using AI-powered grammar correction.

## Features

- Grammar correction in 6 languages (English, Spanish, French, German, Italian, Russian)
- User language preference persistence
- Rate limiting (15 requests/minute per user)
- Automated daily backups
- Error handling and logging

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
   python bot.py
   ```

## File Structure

- `bot.py` - Main bot implementation
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (not in git)
- `user_data.json` - User preferences storage
- `backups/` - Daily backups of user data
- `bot.log` - Application logs

## Error Handling

The bot includes comprehensive error handling for:
- API failures
- Invalid inputs
- Rate limit exceeded
- File system operations

All errors are logged to `bot.log` for debugging.

## License

MIT License 