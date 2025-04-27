import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path
from bot import Bot, UserData, Update
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

class TestBot:
    @pytest.fixture
    def bot(self):
        bot = Bot()
        bot.token = "test_token"
        bot.api_key = "test_api_key"
        return bot

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
        mock_application.updater.start_polling = AsyncMock()

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
            assert mock_application.add_handler.call_count == 5  # Should add 5 handlers: start, help, setlang, currentlang, and message handler
            mock_application.initialize.assert_called_once()
            mock_application.start.assert_called_once()
            mock_application.updater.start_polling.assert_called_once()
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
            
            # Verify that language switch was offered and original message was stored
            update.message.reply_text.assert_called_with(
                "Your message is in FR, but your selected language is EN. "
                "Would you like to switch the language? (yes/no)"
            )
            assert context.user_data.get("original_text") == original_text
            
            # Test language switch acceptance
            original_message = update.message.text
            update.message.text = "yes"
            context.user_data["user"] = user
            context.user_data["detected_lang"] = "fr"

            # Mock save_user_data and call_deepseek_api
            bot.save_user_data = AsyncMock()
            bot.call_deepseek_api = AsyncMock(return_value="[Correction: Bonjour] Hello!")
            
            # Create a new message mock for the original message
            original_update = AsyncMock()
            original_update.message = AsyncMock()
            original_update.message.text = original_text
            original_update.effective_user = update.effective_user
            original_update.effective_chat = update.effective_chat
            
            await bot.handle_language_response(update, context)
            
            # Verify language was switched
            assert user.language == "fr"
            
            # Verify the switch confirmation message was sent
            assert any(
                "Language switched from EN to FR" in str(call.args[0])
                for call in update.message.reply_text.call_args_list
            )
            
            # Verify the original message was processed with new language
            assert any(
                "[Correction: Bonjour] Hello!" in str(call.args[0])
                for call in update.message.reply_text.call_args_list
            )
            
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
        bot.call_deepseek_api = AsyncMock(return_value="[Correction: Bonjour] Hello!")
        
        # Test rejecting language switch
        update.message.text = "no"

        # Create a new message mock for the original message
        original_update = AsyncMock()
        original_update.message = AsyncMock()
        original_update.message.text = original_text
        original_update.effective_user = update.effective_user
        original_update.effective_chat = update.effective_chat

        await bot.handle_language_response(update, context)
        
        # Verify language was not switched
        assert user.language == "en"
        
        # Verify the rejection message was sent
        assert any(
            "Keeping the current language (EN)" in str(call.args[0])
            for call in update.message.reply_text.call_args_list
        )
        
        # Verify the original message was processed with current language
        assert any(
            "[Correction: Bonjour] Hello!" in str(call.args[0])
            for call in update.message.reply_text.call_args_list
        )
        
        # Verify context was cleaned up
        assert "detected_lang" not in context.user_data
        assert "original_text" not in context.user_data

    @pytest.mark.asyncio
    async def test_invalid_language_response(self, bot):
        # Mock update and context
        update = AsyncMock()
        context = MagicMock()
        user = UserData(123)
        context.user_data = {"user": user, "detected_lang": "fr"}
        
        # Test invalid response
        update.message.text = "maybe"
        
        result = await bot.handle_language_response(update, context)
        
        # Verify we stay in the conversation
        assert result == 1  # CONFIRM_LANGUAGE
        update.message.reply_text.assert_called_with(
            "Please respond with 'yes' or 'no'."
        )
        
        # Verify context was not cleaned up
        assert "detected_lang" in context.user_data

if __name__ == '__main__':
    pytest.main()