import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from bot import (
    Bot,
    UserData,
    CONFIRM_LANGUAGE,
    LANG_CONFIRM_KEEP,
    LANG_CONFIRM_SWITCH,
)
from config import Settings
import asyncio

class TestUserData:
    @pytest.fixture
    def user(self):
        return UserData(123)

    def test_can_make_request(self, user):
        # Test rate limiting
        assert user.can_make_request()
        
        # Add maximum requests
        for _ in range(15):
            user.add_request()
        
        # Should be rate limited
        assert not user.can_make_request()

    def test_add_request(self, user):
        initial_count = len(user.last_requests)
        user.add_request()
        assert len(user.last_requests) == initial_count + 1

    def test_clear_conversation_memory(self, user):
        user.add_user_message("a")
        user.add_request()
        user.clear_conversation_memory()
        assert user.message_history == []
        assert user.last_requests == []


class TestBot:
    @pytest.fixture
    def bot(self):
        return Bot(
            settings=Settings(bot_token="test_token", deepseek_api_key="test_api_key")
        )

    @pytest.mark.asyncio
    async def test_run(self, bot):
        # Create mock application class
        mock_application_class = AsyncMock()
        mock_application = AsyncMock()

        # Set up the builder chain
        mock_builder = AsyncMock()
        mock_token_builder = AsyncMock()

        # Configure the mock chain
        mock_application_class.builder = MagicMock(return_value=mock_builder)
        mock_builder.token = MagicMock(return_value=mock_token_builder)
        mock_token_builder.build = MagicMock(return_value=mock_application)

        # Make application methods async
        mock_application.add_handler = MagicMock()
        mock_application.initialize = AsyncMock()
        mock_application.start = AsyncMock()
        mock_application.stop = AsyncMock()
        mock_application.shutdown = AsyncMock()
        mock_updater = MagicMock()
        mock_updater.start_polling = AsyncMock()
        mock_updater.stop = AsyncMock()
        mock_application.updater = mock_updater

        with patch('bot.Application', mock_application_class):
            # Create a task for the bot
            bot_task = asyncio.create_task(bot.run())

            # Wait a short time for initialization
            await asyncio.sleep(0.1)

            # Cancel the bot task
            bot_task.cancel()

            try:
                await bot_task
            except asyncio.CancelledError:
                pass  # Expected when the bot is stopped

            # Verify the initialization chain
            mock_application_class.builder.assert_called_once()
            mock_builder.token.assert_called_with("test_token")
            mock_token_builder.build.assert_called_once()

            # Verify bot setup
            assert mock_application.add_handler.call_count == 8
            mock_application.initialize.assert_called_once()
            mock_application.start.assert_called_once()
            mock_updater.start_polling.assert_called_once()
            mock_updater.stop.assert_called_once()
            mock_application.stop.assert_called_once()
            mock_application.shutdown.assert_called_once()

    def test_load_user_data(self, bot):
        # Test loading user data
        bot.load_user_data()
        assert isinstance(bot.users, dict)

    @pytest.mark.asyncio
    async def test_save_user_data(self, bot):
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        
        with patch('aiofiles.open', return_value=mock_file):
            # Test saving user data
            bot.users[123] = UserData(123)
            await bot.save_user_data()
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_user_data(self, bot):
        mock_src_file = AsyncMock()
        mock_src_file.__aenter__.return_value = mock_src_file
        mock_src_file.read = AsyncMock(return_value='{"test": "data"}')
        
        mock_dst_file = AsyncMock()
        mock_dst_file.__aenter__.return_value = mock_dst_file
        mock_dst_file.write = AsyncMock()
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('aiofiles.open', side_effect=[mock_src_file, mock_dst_file]):
            # Test backup functionality
            await bot.backup_user_data()
            mock_src_file.read.assert_called_once()
            mock_dst_file.write.assert_called_once_with('{"test": "data"}')

    @pytest.mark.asyncio
    async def test_language_detection_and_switching(self, bot):
        # Mock update and context
        update = AsyncMock()
        context = MagicMock()
        user = UserData(123)
        context.user_data = {}

        # Mock message with French text
        update.message.text = "Bonjour"
        update.effective_user.id = 123
        bot.users[123] = user

        # Mock the language detection
        with patch('bot.detect', return_value='fr'):
            original_text = "Bonjour"
            # Set up context.bot for send_chat_action
            context.bot = AsyncMock()
            context.bot.send_chat_action = AsyncMock()
            update.effective_chat = MagicMock(id=123)
            
            # Test message handling with different language
            await bot.correct_message(update, context)

            assert user.message_history == []
            
            # Verify that language switch was offered and original message was stored
            assert update.message.reply_text.call_count == 1
            assert context.user_data.get("original_text") == original_text
            
            # Test language switch acceptance via callback query
            bot.save_user_data = AsyncMock()
            bot.call_deepseek_api = AsyncMock(
                return_value='{"corrected_text":"Bonjour","is_correct":true,"follow_up":"Comment ça va ?","tip":null,"vocab":[]}'
            )

            callback_update = AsyncMock()
            callback_update.effective_chat = update.effective_chat
            callback_update.callback_query.data = LANG_CONFIRM_SWITCH
            callback_update.callback_query.answer = AsyncMock()
            callback_update.callback_query.edit_message_text = AsyncMock()
            context.bot.send_message = AsyncMock()

            await bot.handle_language_callback(callback_update, context)
            
            # Verify language was switched
            assert user.language == "fr"

            context.bot.send_message.assert_called_once()
            bot.save_user_data.assert_called_once()
            
            # Verify context was cleaned up
            assert "detected_lang" not in context.user_data
            assert "original_text" not in context.user_data

    @pytest.mark.asyncio
    async def test_language_switch_rejection(self, bot):
        # Mock update and context
        update = AsyncMock()
        context = MagicMock()
        user = UserData(123)
        context.user_data = {"user": user, "detected_lang": "fr"}
        
        # Set initial language
        user.language = "en"
        
        # Add original message to context
        original_text = "Bonjour"
        context.user_data["original_text"] = original_text
        
        # Set up context.bot for send_chat_action
        context.bot = AsyncMock()
        context.bot.send_chat_action = AsyncMock()
        update.effective_chat = MagicMock(id=123)
        
        # Mock call_deepseek_api for processing original message
        bot.call_deepseek_api = AsyncMock(
            return_value='{"corrected_text":"Bonjour","is_correct":true,"follow_up":"Comment ça va ?","tip":null,"vocab":[]}'
        )
        
        context.bot.send_message = AsyncMock()
        callback_update = AsyncMock()
        callback_update.effective_chat = update.effective_chat
        callback_update.callback_query.data = LANG_CONFIRM_KEEP
        callback_update.callback_query.answer = AsyncMock()
        callback_update.callback_query.edit_message_text = AsyncMock()

        await bot.handle_language_callback(callback_update, context)
        
        # Verify language was not switched
        assert user.language == "en"
        context.bot.send_message.assert_called_once()
        
        # Verify context was cleaned up
        assert "detected_lang" not in context.user_data
        assert "original_text" not in context.user_data

    @pytest.mark.asyncio
    async def test_invalid_language_response(self, bot):
        # Kept for backwards compatibility; new flow uses inline buttons
        assert CONFIRM_LANGUAGE == 1

    @pytest.mark.asyncio
    async def test_forget_command_clears_memory_and_context(self, bot):
        user = UserData(42)
        user.language = "fr"
        user.add_user_message("secret")
        user.add_request()
        bot.users[42] = user

        update = AsyncMock()
        update.effective_user.id = 42
        context = MagicMock()
        context.user_data = {"pending": True}

        await bot.forget_command(update, context)

        assert user.message_history == []
        assert user.last_requests == []
        assert user.language == "fr"
        assert context.user_data == {}
        update.message.reply_text.assert_called_once()
        assert "cleared" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_privacy_command_replies(self, bot):
        update = AsyncMock()
        context = MagicMock()
        await bot.privacy_command(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "DeepSeek" in text
        assert "user_data.json" in text

    @pytest.mark.asyncio
    async def test_json_reply_formatting(self, bot):
        update = AsyncMock()
        context = MagicMock()
        context.user_data = {}
        context.bot = AsyncMock()
        context.bot.send_chat_action = AsyncMock()
        update.effective_user.id = 5
        update.effective_chat = MagicMock(id=5)
        update.message.text = "I goes to the store"

        bot.users[5] = UserData(5)
        bot.users[5].language = "en"

        bot.call_deepseek_api = AsyncMock(
            return_value='{"corrected_text":"I go to the store","is_correct":false,"follow_up":"What do you like to buy there?","tip":"Use go with I/you/we/they.","vocab":["to buy","grocery store"]}'
        )

        await bot.correct_message(update, context)

        sent = update.message.reply_text.call_args[0][0]
        assert "Correction:" in sent
        assert "I go to the store" in sent
        assert "Tip:" in sent
        assert "Vocab:" in sent


class TestUserDataMessageHistory:
    def test_add_message_with_timestamp(self):
        user = UserData(123)
        user.add_user_message("hello")
        user.add_assistant_message("hi")

        assert "timestamp" in user.message_history[0]
        assert "timestamp" in user.message_history[1]
        assert isinstance(user.message_history[0]["timestamp"], datetime)
        assert isinstance(user.message_history[1]["timestamp"], datetime)

    def test_message_history_trim(self):
        user = UserData(123)
        for i in range(6):
            user.add_user_message(f"user message {i}")
            user.add_assistant_message(f"assistant message {i}")

        assert len(user.message_history) == 10
        assert user.message_history[0]["content"] == "user message 1"
        assert user.message_history[1]["content"] == "assistant message 1"


class TestCallDeepSeekApi:
    @pytest.fixture
    def bot(self):
        return Bot(
            settings=Settings(bot_token="test_token", deepseek_api_key="test_api_key")
        )

    @pytest.fixture
    def user_with_old_messages(self, bot):
        user = UserData(123)
        user.add_user_message("old message 1")
        user.add_assistant_message("old response 1")
        user.add_user_message("old message 2")
        user.add_assistant_message("old response 2")
        return user

    @pytest.mark.asyncio
    async def test_call_deepseek_api_with_old_messages(self, bot, user_with_old_messages):
        captured: dict = {}

        async def fake(api_key, payload):
            captured["api_key"] = api_key
            captured["payload"] = payload
            return "test response"

        with patch("bot.deepseek_chat_completion", side_effect=fake):
            out = await bot.call_deepseek_api(user_with_old_messages)

        assert out == "test response"
        assert captured["api_key"] == "test_api_key"
        messages = captured["payload"]["messages"]
        assert len(messages) == 5
        assert messages[1]["content"] == "old message 1"
        assert messages[2]["content"] == "old response 1"
        assert messages[3]["content"] == "old message 2"
        assert messages[4]["content"] == "old response 2"

    @pytest.mark.asyncio
    async def test_call_deepseek_api_with_expired_messages(self, bot, user_with_old_messages):
        old_time = datetime.now() - timedelta(hours=25)
        user_with_old_messages.message_history.append(
            {
                "role": "user",
                "content": "expired message",
                "timestamp": old_time,
            }
        )
        user_with_old_messages.add_user_message("recent message")

        captured: dict = {}

        async def fake(api_key, payload):
            captured["payload"] = payload
            return "ok"

        with patch("bot.deepseek_chat_completion", side_effect=fake):
            await bot.call_deepseek_api(user_with_old_messages)

        messages = captured["payload"]["messages"]
        contents = [m["content"] for m in messages]
        assert "expired message" not in contents
        assert "recent message" in contents

    @pytest.mark.asyncio
    async def test_call_deepseek_api_with_all_expired_messages(self, bot):
        user = UserData(123)
        old_time = datetime.now() - timedelta(hours=25)
        user.message_history.append(
            {
                "role": "user",
                "content": "expired message",
                "timestamp": old_time,
            }
        )

        response = await bot.call_deepseek_api(user)

        assert len(user.message_history) == 0
        assert response == (
            "Your previous conversation has expired. Please start a new conversation."
        )


if __name__ == '__main__':
    pytest.main()