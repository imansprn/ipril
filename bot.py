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
        logging.StreamHandler()  # Add console output
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

RATE_LIMIT = 15  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# System prompt for DeepSeek API
SYSTEM_PROMPT = """You are a grammar correction assistant. Your task is to:
1. Correct grammar mistakes in the given text
2. Provide a friendly follow-up question related to the corrected content
3. Format your response as: "[Correction: CORRECTED_TEXT] FOLLOW_UP_QUESTION"

Example:
Input: "He go to school"
Output: "[Correction: He goes to school] Do you like school?"
"""

class UserData:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.language = "en"  # Default language
        self.last_requests = []

    def can_make_request(self) -> bool:
        now = datetime.now()
        # Remove requests older than the rate limit window
        self.last_requests = [
            req_time for req_time in self.last_requests
            if (now - req_time).total_seconds() < RATE_LIMIT_WINDOW
        ]
        return len(self.last_requests) < RATE_LIMIT

    def add_request(self):
        self.last_requests.append(datetime.now())

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
            "/currentlang - Show current language\n\n"
            "Just send me a message and I'll help correct it!"
        )
        await update.message.reply_text(welcome_message)

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

    async def call_deepseek_api(self, text: str, language: str) -> str:
        """Call DeepSeek API for grammar correction"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Correct the following {SUPPORTED_LANGUAGES[language]} text and provide a follow-up question: {text}"
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    response_text = result["choices"][0]["message"]["content"]
                    
                    # Extract the correction from the response
                    if response_text.startswith("[Correction: ") and "] " in response_text:
                        correction = response_text.split("[Correction: ")[1].split("] ")[0]
                        follow_up = response_text.split("] ")[1]
                        
                        # If the correction is the same as the input, just return the follow-up question
                        if correction.strip() == text.strip():
                            return follow_up
                            
                    return response_text
                else:
                    error_text = await response.text()
                    logger.error(f"DeepSeek API error: {error_text}")
                    raise Exception(f"API error: {error_text}")

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

        try:
            corrected_text = await self.call_deepseek_api(text, user.language)
            await update.message.reply_text(corrected_text)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error while processing your message. Please try again later."
            )

    async def run(self):
        """Run the bot"""
        try:
            # Create backups directory if it doesn't exist
            Path("backups").mkdir(exist_ok=True)

            # Initialize the bot
            application = Application.builder().token(self.token).build()

            # Add handlers
            application.add_handler(CommandHandler("start", self.start))
            application.add_handler(CommandHandler("setlang", self.set_language))
            application.add_handler(CommandHandler("currentlang", self.current_language))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.correct_message))

            # Start the bot
            logger.info("Starting bot...")
            await application.initialize()
            await application.start()
            
            # Run the bot with proper error handling
            try:
                await application.run_polling(allowed_updates=Update.ALL_TYPES)
            except asyncio.CancelledError:
                logger.info("Bot received cancellation signal")
            finally:
                await application.stop()
                await application.shutdown()

        except Conflict as e:
            logger.error(f"Bot conflict error: {e}")
            # Wait for a short time before retrying
            await asyncio.sleep(5)
            # Try to run the bot again
            await self.run()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

if __name__ == "__main__":
    bot = Bot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        raise 