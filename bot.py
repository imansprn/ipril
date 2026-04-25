#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
from dotenv import load_dotenv

from config import Settings
from deepseek_client import deepseek_chat_completion
from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from langdetect import detect, LangDetectException, DetectorFactory

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

# Configure language detection
DetectorFactory.seed = 0  # For consistent results
DetectorFactory.lang_list = list(SUPPORTED_LANGUAGES.keys())  # Only detect supported languages

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

SYSTEM_PROMPT = """You are a language-learning conversation tutor.

Given the user's message, produce a JSON object ONLY (no markdown, no code fences, no extra text).

Rules:
- Keep everything (corrected text, follow-up, tip, vocab) in the SAME language as the user's chosen language.
- If the user's message is already correct, keep corrected_text identical and set is_correct=true.
- corrected_text should preserve the user's meaning and tone.
- follow_up must be a single question that continues the conversation.

Return exactly these fields:
{
  "corrected_text": string,
  "is_correct": boolean,
  "follow_up": string,
  "tip": string | null,
  "vocab": [string, string] | []
}
"""

CONFIRM_LANGUAGE = 1
LANG_CONFIRM_SWITCH = "lang_confirm:switch"
LANG_CONFIRM_KEEP = "lang_confirm:keep"


class UserData:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.language = "en"  # Default language
        self.last_requests = []
        self.message_history = []  # Each item: {"role": "user"/"assistant", "content": "...", "timestamp": datetime}
        self._recent_correct_flags = deque(maxlen=20)

    def can_make_request(self) -> bool:
        now = datetime.now()
        self.last_requests = [
            req_time for req_time in self.last_requests
            if (now - req_time).total_seconds() < RATE_LIMIT_WINDOW
        ]
        if len(self.last_requests) >= RATE_LIMIT:
            return False
        self.last_requests.append(now)
        return True

    def add_request(self):
        self.last_requests.append(datetime.now())

    def record_message_quality(self, was_already_correct: bool) -> None:
        self._recent_correct_flags.append(bool(was_already_correct))

    @property
    def proficiency(self) -> str:
        """
        Heuristic, adaptive proficiency level.
        - "beginner" when we see frequent corrections
        - "intermediate" when messages are often already correct
        """
        if len(self._recent_correct_flags) < 6:
            return "beginner"
        correct_rate = sum(self._recent_correct_flags) / len(self._recent_correct_flags)
        return "intermediate" if correct_rate >= 0.7 else "beginner"

    def add_user_message(self, text: str):
        """Add a user message to history (keep max 5 pairs)"""
        self.message_history.append({
            "role": "user", 
            "content": text,
            "timestamp": datetime.now()  # Add timestamp to new messages
        })
        self._trim_history()

    def add_assistant_message(self, text: str):
        """Add a bot/assistant message to history"""
        self.message_history.append({
            "role": "assistant", 
            "content": text,
            "timestamp": datetime.now()  # Add timestamp to new messages
        })
        self._trim_history()

    def _trim_history(self):
        """Keep only last 5 user+assistant pairs (max 10 messages)"""
        if len(self.message_history) > 10:
            self.message_history = self.message_history[-10:]

    def clear_conversation_memory(self) -> None:
        """Drop in-memory chat history and per-minute request timestamps (privacy / reset)."""
        self.message_history = []
        self.last_requests = []


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        # drop first and last fence lines if present
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return s


def parse_model_json_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse the model response JSON.
    Returns None if parsing fails.
    """
    s = _strip_code_fences(text)
    # Try to extract first JSON object if the model included extra text
    if "{" in s and "}" in s:
        start = s.find("{")
        end = s.rfind("}")
        candidate = s[start : end + 1]
    else:
        candidate = s
    try:
        data = json.loads(candidate)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def format_tutor_reply(lang_code: str, original_text: str, payload: Dict[str, Any]) -> str:
    """
    Render a user-facing message from the model JSON payload.
    """
    label = CORRECTION_LABELS.get(lang_code, "Correction:")
    corrected_text = str(payload.get("corrected_text") or "").strip()
    follow_up = str(payload.get("follow_up") or "").strip()
    tip = payload.get("tip")
    vocab = payload.get("vocab") or []

    if not corrected_text:
        corrected_text = original_text
    if not follow_up:
        follow_up = ""

    parts = [f"[{label} {corrected_text}]"]
    if tip:
        parts.append(f"Tip: {str(tip).strip()}")
    if vocab and isinstance(vocab, list):
        vocab_items = [str(v).strip() for v in vocab if str(v).strip()]
        if vocab_items:
            parts.append("Vocab: " + ", ".join(vocab_items[:2]))
    if follow_up:
        parts.append(follow_up)
    return "\n".join(parts).strip()


class Bot:
    def __init__(self, settings: Optional[Settings] = None):
        if settings is None:
            settings = Settings.from_env()
        self.token = settings.bot_token
        self.api_key = settings.deepseek_api_key
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
                        # Backwards-compatible: older files only have "language"
                        if "recent_correct_flags" in user_data:
                            self.users[int(user_id)]._recent_correct_flags.extend(
                                [bool(x) for x in user_data["recent_correct_flags"]][-20:]
                            )
        except Exception as e:
            logger.error(f"Error loading user data: {e}")

    async def save_user_data(self):
        """Save user data to JSON file"""
        try:
            data = {
                str(user_id): {
                    "language": user.language,
                    "recent_correct_flags": list(user._recent_correct_flags),
                }
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
            "/privacy - How your data is used\n"
            "/forget - Clear this chat's conversation memory\n"
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
            "/privacy - Data use and third parties\n"
            "/forget - Clear conversation memory (keeps language preference)\n"
            "/help - This help message\n\n"
            "Supported languages: en, es, fr, de, it, ru"
        )
        await update.message.reply_text(help_message)

    async def privacy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Explain what leaves the device and what is stored locally."""
        text = (
            "Privacy (short version)\n\n"
            "• Messages you send for correction are forwarded to DeepSeek "
            "(api.deepseek.com) as chat completion requests. Do not send secrets.\n"
            "• On this server we keep your chosen language in user_data.json "
            "and short in-memory conversation context to power replies.\n"
            "• /forget clears that in-memory conversation and rate-limit timestamps "
            "for your account. Your saved language preference stays unless you change it with /setlang.\n"
            "• Logs may contain errors (snippets only); avoid sending highly sensitive text."
        )
        await update.message.reply_text(text)

    async def forget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear conversation memory for this user."""
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)
            await self.save_user_data()

        self.users[user_id].clear_conversation_memory()
        context.user_data.clear()
        await update.message.reply_text(
            "Conversation memory cleared for your account. "
            "Your language preference is unchanged. Send a new message anytime."
        )

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

        user = self.users[user_id]
        lang_code = user.language
        await update.message.reply_text(
            f"Your current language is {SUPPORTED_LANGUAGES[lang_code]} (mode: {user.proficiency})"
        )

    async def call_deepseek_api(self, user: UserData) -> str:
        """Call DeepSeek API with full chat history"""
        # Check if there are any messages in history
        if not user.message_history:
            return "Please send me a message to correct."

        # For now, we'll only check timestamps on new messages
        # Existing messages without timestamps will be treated as valid
        last_message = user.message_history[-1]
        
        # Only check timestamp if it exists (for new messages)
        if "timestamp" in last_message:
            last_message_time = last_message["timestamp"]
            time_diff = datetime.now() - last_message_time
            
            if time_diff.total_seconds() > 24 * 3600:  # 24 hours in seconds
                # Clear the message history if it's too old
                user.message_history = []
                return "Your previous conversation has expired. Please start a new conversation."

        # Use the user's set language instead of trying to detect it
        input_lang = user.language

        system_prompt = SYSTEM_PROMPT
        if user.proficiency == "beginner":
            system_prompt += (
                "\nGuidelines:\n"
                "- Keep the follow-up question short and simple.\n"
                "- Prefer common vocabulary and simple sentence structures.\n"
                "- If there is a clear single rule causing the mistake, hint it briefly in the follow-up.\n"
            )
        else:
            system_prompt += (
                "\nGuidelines:\n"
                "- Keep the follow-up question natural and conversational.\n"
                "- Use richer vocabulary, but stay understandable.\n"
                "- Do not add explicit teaching unless the user text is very incorrect.\n"
            )
        
        # Create a copy of messages without timestamps for the API
        # Only include messages that are either:
        # 1. Less than 24 hours old (if they have timestamps)
        # 2. Don't have timestamps (old messages)
        history_messages = []
        now = datetime.now()
        for msg in user.message_history:
            # Skip messages with timestamps that are more than 24 hours old
            if "timestamp" in msg:
                time_diff = now - msg["timestamp"]
                if time_diff.total_seconds() > 24 * 3600:
                    continue
            
            message = {
                "role": msg["role"],
                "content": msg["content"]
            }
            history_messages.append(message)

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system_prompt}] + history_messages,
            "temperature": 0.7,
            "max_tokens": 300,
        }

        return await deepseek_chat_completion(self.api_key, payload)

    async def prompt_language_switch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user: UserData = context.user_data.get("user")
        detected_lang = context.user_data.get("detected_lang")
        if not user or not detected_lang:
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Switch", callback_data=LANG_CONFIRM_SWITCH),
                    InlineKeyboardButton("Keep", callback_data=LANG_CONFIRM_KEEP),
                ]
            ]
        )
        await update.message.reply_text(
            f"Your message looks like {detected_lang.upper()}, but your selected language is {user.language.upper()}. "
            "Switch?",
            reply_markup=keyboard,
        )

    async def handle_language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button for switching/keeping language, then process the stored message."""
        query = update.callback_query
        if query:
            await query.answer()

        user: UserData = context.user_data.get("user")
        detected_lang = context.user_data.get("detected_lang")
        original_text = context.user_data.get("original_text")
        if not user or not detected_lang or not original_text:
            return

        if query and query.data == LANG_CONFIRM_SWITCH:
            old_lang = user.language
            user.language = detected_lang
            await self.save_user_data()
            await query.edit_message_text(
                f"Language switched from {old_lang.upper()} to {detected_lang.upper()}."
            )
        elif query and query.data == LANG_CONFIRM_KEEP:
            await query.edit_message_text(
                f"Keeping the current language ({user.language.upper()})."
            )
        else:
            return

        user.add_user_message(original_text)
        model_text = await self.call_deepseek_api(user)
        parsed = parse_model_json_response(model_text)
        if parsed is None:
            # Fallback: treat as plain text
            user.record_message_quality(False)
            user.add_assistant_message(model_text)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=model_text)
        else:
            is_correct = bool(parsed.get("is_correct", False))
            reply = format_tutor_reply(user.language, original_text, parsed)
            user.record_message_quality(is_correct)
            user.add_assistant_message(reply)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=reply)

        context.user_data.pop("detected_lang", None)
        context.user_data.pop("original_text", None)
        context.user_data.pop("user", None)

    async def correct_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.users:
            self.users[user_id] = UserData(user_id)
            await self.save_user_data()

        user = self.users[user_id]
        if not user.can_make_request():
            await update.message.reply_text(
                "You've reached the rate limit. Please wait a minute before sending more messages."
            )
            return ConversationHandler.END

        text = update.message.text

        # Skip language detection for yes/no responses and short messages
        text_lower = text.strip().lower()
        if text_lower in ["yes", "no"] or len(text_lower) < 3:
            detected_lang = user.language
        else:
            # Detect the language of the incoming message
            try:
                detected_lang = detect(text)
                # Only consider supported languages
                if detected_lang not in SUPPORTED_LANGUAGES:
                    detected_lang = user.language
            except LangDetectException as e:
                logger.debug(f"Language detection failed: {e}")
                detected_lang = user.language  # Keep current language on detection failure

        if detected_lang != user.language and detected_lang in SUPPORTED_LANGUAGES:
            context.user_data["user"] = user
            context.user_data["detected_lang"] = detected_lang
            context.user_data["original_text"] = text  # Store the original message
            await self.prompt_language_switch(update, context)
            return ConversationHandler.END

        user.add_user_message(text)

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            model_text = await self.call_deepseek_api(user)
            parsed = parse_model_json_response(model_text)
            if parsed is None:
                await update.message.reply_text(model_text)
                user.record_message_quality(False)
                user.add_assistant_message(model_text)
            else:
                reply = format_tutor_reply(user.language, text, parsed)
                await update.message.reply_text(reply)
                user.record_message_quality(bool(parsed.get("is_correct", False)))
                user.add_assistant_message(reply)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error while processing your message. Please try again later."
            )
            return ConversationHandler.END

        return ConversationHandler.END

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
            application.add_handler(CommandHandler("privacy", self.privacy_command))
            application.add_handler(CommandHandler("forget", self.forget_command))
            application.add_handler(CallbackQueryHandler(self.handle_language_callback, pattern="^lang_confirm:"))

            conv_handler = ConversationHandler(
                entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, self.correct_message)],
                states={
                    CONFIRM_LANGUAGE: [],
                },
                fallbacks=[],
            )
            application.add_handler(conv_handler)

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
                    updater = getattr(application, "updater", None)
                    if updater is not None:
                        await updater.stop()
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
    except RuntimeError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        raise
