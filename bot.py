#!/usr/bin/env python3
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import aiofiles
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import Conflict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ru": "Russian",
}

CORRECTION_LABELS = {
    "en": "Correction:",
    "es": "Corrección:",
    "fr": "Correction:",
    "de": "Korrektur:",
    "it": "Correzione:",
    "ru": "Исправление:"
}

RATE_LIMIT = 15  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# System prompt for DeepSeek API
SYSTEM_PROMPT = """You are a grammar correction assistant. Your task is to:
1. Correct grammar mistakes in the given text while keeping it in the same language
2. Provide a friendly follow-up question in the user's chosen language
3. Format your response as: "[CORRECTION_LABEL CORRECTED_TEXT] FOLLOW_UP_QUESTION"

Example for English input:
Input: "He go to school"
Output: "[Correction: He goes to school] Do you like school?"

Example for Spanish input:
Input: "Yo ir al parque"
Output: "[Corrección: Yo voy al parque] ¿Qué te gusta hacer en el parque?"

Example for French input:
Input: "Je mange un pomme"
Output: "[Correction: Je mange une pomme] Aimes-tu les fruits?"

Example for German input:
Input: "Ich gehe in der Park"
Output: "[Korrektur: Ich gehe in den Park] Was machst du gerne im Park?"

Example for Italian input:
Input: "Io mangiare la pizza"
Output: "[Correzione: Io mangio la pizza] Qual è la tua pizza preferita?"

Example for Russian input:
Input: "Я ходить в магазин"
Output: "[Исправление: Я хожу в магазин] Что ты обычно покупаешь в магазине?"
"""


class UserData:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.language = "en"  # Default language
        self.last_requests = []
        self.message_history = []  # 👈 Each item: {"role": "user"/"assistant", "content": "..."}

    def can_make_request(self) -> bool:
        now = datetime.now()
        self.last_requests = [
            req_time for req_time in self.last_requests
            if (now - req_time).total_seconds() < RATE_LIMIT_WINDOW
        ]
        return len(self.last_requests) < RATE_LIMIT

    def add_request(self):
        self.last_requests.append(datetime.now())

    def add_user_message(self, text: str):
        """Add a user message to history (keep max 5 pairs)"""
        self.message_history.append({"role": "user", "content": text})
        self._trim_history()

    def add_assistant_message(self, text: str):
        """Add a bot/assistant message to history"""
        self.message_history.append({"role": "assistant", "content": text})
        self._trim_history()

    def _trim_history(self):
        """Keep only last 5 user+assistant pairs (max 10 messages)"""
        if len(self.message_history) > 10:
            self.message_history = self.message_history[-10:]


class Bot:
    def __init__(self):
        self.token = os.getenv("BOT_TOKEN")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.users: Dict[int, UserData] = {}
        self.data_file = Path("user_data.json")
        self.load_user_data()

    def load_user_data(self):
        """Load user data from JSON file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    for user_id, user_data in data.items():
                        self.users[int(user_id)] = UserData(int(user_id))
                        self.users[int(user_id)].language = user_data["language"]
        except Exception as e:
            logger.error(f"Error loading user data: {e}")

    async def save_user_data(self):
        """Save user data to JSON file"""
        try:
            data = {
                str(user_id): {"language": user.language}
                for user_id, user in self.users.items()
            }
            async with aiofiles.open(self.data_file, "w") as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving user data: {e}")

    async def backup_user_data(self):
        """Create a backup of user data"""
        try:
            backup_file = Path(f"backups/user_data_{datetime.now().strftime('%Y%m%d')}.json")
            backup_file.parent.mkdir(exist_ok=True)
            if self.data_file.exists():
                async with aiofiles.open(self.data_file, "r") as src, \
                        aiofiles.open(backup_file, "w") as dst:
                    await dst.write(await src.read())
        except Exception as e:
            logger.error(f"Error creating backup: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)
            await self.save_user_data()

        welcome_message = (
            "Welcome to Ipril - Your Grammar Assistant! 🎓\n\n"
            "I can help you improve your writing in 6 languages:\n"
            "🇬🇧 English (en)\n"
            "🇪🇸 Spanish (es)\n"
            "🇫🇷 French (fr)\n"
            "🇩🇪 German (de)\n"
            "🇮🇹 Italian (it)\n"
            "🇷🇺 Russian (ru)\n\n"
            "Commands:\n"
            "/setlang [code] - Change language\n"
            "/currentlang - Show current language\n"
            "/help - Show help message\n\n"
            "Just send me a message and I'll help correct it!"
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        help_message = (
            "📚 Ipril Help Guide 📚\n\n"
            "How to use me:\n"
            "1. Send me any text message\n"
            "2. I'll correct the grammar and ask a follow-up question\n"
            "3. Continue the conversation naturally!\n\n"
            "Available commands:\n"
            "/start - Welcome message\n"
            "/setlang [code] - Change language (e.g., /setlang es)\n"
            "/currentlang - Show your current language\n"
            "/help - This help message\n\n"
            "Supported languages: en, es, fr, de, it, ru"
        )
        await update.message.reply_text(help_message)

    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /setlang command"""
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)

        if not context.args:
            await update.message.reply_text(
                "Please specify a language code. Example: /setlang en"
            )
            return

        lang_code = context.args[0].lower()
        if lang_code not in SUPPORTED_LANGUAGES:
            await update.message.reply_text(
                f"Unsupported language. Available codes: {', '.join(SUPPORTED_LANGUAGES.keys())}"
            )
            return

        self.users[user_id].language = lang_code
        await self.save_user_data()
        await update.message.reply_text(
            f"Language set to {SUPPORTED_LANGUAGES[lang_code]}!"
        )

    async def current_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /currentlang command"""
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)
            await self.save_user_data()

        lang_code = self.users[user_id].language
        await update.message.reply_text(
            f"Your current language is {SUPPORTED_LANGUAGES[lang_code]}"
        )

    async def call_deepseek_api(self, user: UserData) -> str:
        """Call DeepSeek API with full chat history"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Get the last user message to determine input language
        last_user_message = next(
            (msg["content"] for msg in reversed(user.message_history) 
             if msg["role"] == "user"),
            ""
        )

        # Determine input language based on the message content
        input_lang = "en"  # Default to English
        for lang_code in SUPPORTED_LANGUAGES:
            if any(word in last_user_message for word in [
                "je", "tu", "il", "elle",  # French
                "yo", "tú", "él", "ella",  # Spanish
                "ich", "du", "er", "sie",   # German
                "io", "tu", "lui", "lei",   # Italian
                "я", "ты", "он", "она"      # Russian
            ]):
                input_lang = lang_code
                break

        system_prompt = SYSTEM_PROMPT.replace(
            "CORRECTION_LABEL", 
            CORRECTION_LABELS.get(input_lang, "Correction:")
        )
        history_messages = user.message_history.copy()

        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system_prompt}] + history_messages,
            "temperature": 0.7,
            "max_tokens": 300
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_text = result["choices"][0]["message"]["content"]
                        return response_text
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error {response.status}: {error_text}")
                        return "Sorry, I encountered an error with the grammar service. Please try again later."
            except Exception as e:
                logger.error(f"Network error calling DeepSeek API: {e}")
                return "Sorry, I encountered an error with the grammar service. Please try again later."

    async def correct_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages for grammar correction"""
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)
            await self.save_user_data()

        user = self.users[user_id]
        if not user.can_make_request():
            await update.message.reply_text(
                "You've reached the rate limit. Please wait a minute before sending more messages."
            )
            return

        user.add_request()
        text = update.message.text
        user.add_user_message(text)  # 👈 SAVE user message first

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            corrected_text = await self.call_deepseek_api(user)

            # Check if the corrected text is the same as the original message
            if corrected_text.startswith(f"[Correction: {text}]"):
                # If no correction is needed, simply say the message is correct
                await update.message.reply_text("Your message is already correct! ✅")
            else:
                await update.message.reply_text(corrected_text)

            user.add_assistant_message(corrected_text)  # 👈 SAVE bot reply

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error while processing your message. Please try again later."
            )

    async def run(self):
        """Run the bot with proper event loop handling"""
        try:
            # Create backups directory if it doesn't exist
            Path("backups").mkdir(exist_ok=True)

            # Initialize the bot
            application = Application.builder().token(self.token).build()

            # Add handlers
            application.add_handler(CommandHandler("start", self.start))
            application.add_handler(CommandHandler("help", self.help_command))
            application.add_handler(CommandHandler("setlang", self.set_language))
            application.add_handler(CommandHandler("currentlang", self.current_language))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.correct_message))

            logger.info("Starting bot...")

            # Run the bot with proper lifecycle management
            await application.initialize()
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            # Keep the bot running until interrupted
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Bot shutdown requested...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
        finally:
            # Proper shutdown sequence
            if 'application' in locals():
                try:
                    await application.updater.stop()
                    await application.stop()
                    await application.shutdown()
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    try:
        bot = Bot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        raise
