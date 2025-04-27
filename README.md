# Ipril - Grammar Assistant Bot

<p align="center"><img src="https://raw.githubusercontent.com/imansprn/ipril/main/assets/logo.png" width="360"></p>

<p align="center">
  <a href="https://github.com/imansprn/ipril/actions/workflows/bot.yml"><img src="https://github.com/imansprn/ipril/actions/workflows/bot.yml/badge.svg" alt="Tests"></img></a>
  <a href="https://codecov.io/gh/imansprn/ipril"><img src="https://codecov.io/gh/imansprn/ipril/branch/main/graph/badge.svg" alt="Coverage"></img></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10-blue.svg" alt="Python Version"></img></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></img></a>
</p>

You can try this bot on Telegram by searching for [@IprilBot](https://t.me/IprilBot) or clicking the link to start a conversation.

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

## Example Results

Here are some examples of how the bot corrects grammar and engages in conversation:

### 🇺🇸 English (en)
```
User: "I goes to the store yesterday"
Bot: "[Correction: I went to the store yesterday] What did you buy at the store?"
```

### 🇪🇸 Spanish (es)
```
User: "Yo ir al parque mañana"
Bot: "[Correction: Yo iré al parque mañana] ¿Qué te gusta hacer en el parque?"
```

### 🇫🇷 French (fr)
```
User: "Je mange un pomme"
Bot: "[Correction: Je mange une pomme] Aimes-tu les fruits en général?"
```

### 🇩🇪 German (de)
```
User: "Ich gehe in der Park"
Bot: "[Correction: Ich gehe in den Park] Was machst du gerne im Park?"
```

### 🇮🇹 Italian (it)
```
User: "Io mangiare la pizza"
Bot: "[Correction: Io mangio la pizza] Qual è la tua pizza preferita?"
```

### 🇷🇺 Russian (ru)
```
User: "Я ходить в магазин"
Bot: "[Correction: Я хожу в магазин] Что ты обычно покупаешь в магазине?"
```

The bot not only corrects grammar but also:
- Maintains conversation context
- Asks relevant follow-up questions
- Supports 6 languages
- Remembers user preferences
- Has a rate limit of 15 requests per minute

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

3. Run tests:
   ```bash
   pytest tests/ -v
   ```

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

- `bot.py` - Main bot implementation
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