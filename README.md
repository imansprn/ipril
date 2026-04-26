# Ipril - Language Tutor Bot

<p align="center"><img src="https://raw.githubusercontent.com/imansprn/ipril/main/assets/logo.png" width="360"></p>

<p align="center">
  <a href="https://github.com/imansprn/ipril/actions/workflows/bot.yml"><img src="https://github.com/imansprn/ipril/actions/workflows/bot.yml/badge.svg" alt="Tests"></img></a>
  <a href="https://codecov.io/gh/imansprn/ipril"><img src="https://codecov.io/gh/imansprn/ipril/branch/main/graph/badge.svg" alt="Coverage"></img></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python Version"></img></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></img></a>
</p>

You can try this bot on Telegram by searching for [@IprilBot](https://t.me/IprilBot) or clicking the link to start a conversation.

A Telegram bot that helps users learn languages through conversation with AI-powered corrections, tips, and follow-up questions.

## Features

- Grammar correction in 6 languages (English, Spanish, French, German, Italian, Russian)
- User language preference persistence
- Rate limiting (15 requests/minute per user)
- Adaptive conversation difficulty (beginner/intermediate)
- `/privacy` and `/forget` for transparency and clearing chat memory
- Validated configuration (missing `BOT_TOKEN` / `DEEPSEEK_API_KEY` fails fast)
- DeepSeek HTTP calls with timeouts
- Automated daily backups
- Error handling and logging
- Unit tests for core functionality

## Commands

- `/start` - Welcome message with instructions
- `/setlang [code]` - Change language preference
- `/currentlang` - Show current language
- `/privacy` - How your data is used (DeepSeek, local storage)
- `/forget` - Clear conversation memory (keeps saved language)

## Example Results

Here are some examples of how the bot corrects grammar and engages in conversation:

### 🇺🇸 English (en)
```
User: /setlang en
Bot: Language set to English!

User: "I goes to the store"
Bot:
[Correction: I go to the store]
Tip: Use "go" with I/you/we/they (not "goes").
Vocab: grocery store, to buy
What do you like to buy there?
```

### 🇪🇸 Spanish (es)
```
User: /setlang es
Bot: ¡Idioma configurado a español!

User: "Yo ir al parque"
Bot:
[Corrección: Yo voy al parque]
Consejo: El verbo “ir” cambia: yo voy.
Vocabulario: parque, pasear
¿Qué te gusta hacer en el parque?
```

### 🇫🇷 French (fr)
```
User: /setlang fr
Bot: Langue définie sur français !

User: "Je vais au parc"
Bot:
[Correction: Je vais au parc]
Qu'aimes-tu faire au parc?
```

### 🇩🇪 German (de)
```
User: /setlang de
Bot: Sprache auf Deutsch eingestellt!

User: "Ich gehen ins Kino"
Bot:
[Korrektur: Ich gehe ins Kino]
Tipp: Das Verb wird konjugiert: ich gehe (nicht „ich gehen“).
Vokabeln: Kino, gehen
Welche Filme schaust du gerne?
```

### 🇮🇹 Italian (it)
```
User: /setlang it
Bot: Lingua impostata su italiano!

User: "Io mangiare la pizza"
Bot:
[Correzione: Io mangio la pizza]
Suggerimento: Il verbo si coniuga: io mangio (non “io mangiare”).
Vocabolario: pizza, mangiare
Qual è la tua pizza preferita?
```

### 🇷🇺 Russian (ru)
```
User: /setlang ru
Bot: Язык установлен на русский!

User: "Я ходить в магазин"
Bot:
[Исправление: Я хожу в магазин]
Подсказка: Глагол нужно спрягать: я хожу (не «я ходить»).
Слова: магазин, покупать
Что ты обычно покупаешь в магазине?
```

The bot not only corrects grammar but also:
- Maintains conversation context
- Corrects grammar in the input language (including the "Correction:" text)
- Asks follow-up questions in the chosen language
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

Note: Messages you send for correction are forwarded to DeepSeek for processing. Avoid sending secrets. See `/privacy` in the bot for details.

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
- Configuration validation (`config.py`)

Run tests locally:
```bash
pytest tests/ -v
```

## File Structure

- `bot.py` - Main bot implementation
- `config.py` - Environment settings validation
- `deepseek_client.py` - DeepSeek API HTTP client (timeouts)
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

Security note: avoid sharing or committing `bot.log`. Logs may include URLs and snippets from upstream errors.

## License

MIT License 