import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path
from main import Bot, UserData
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
        mock_application.initialize = AsyncMock()
        mock_application.start = AsyncMock()
        mock_application.run_polling = AsyncMock()
        mock_application.stop = AsyncMock()
        mock_application.add_handler = MagicMock()
        
        with patch('main.Application', mock_application_class):
            try:
                # Test bot initialization
                await bot.run()
            except asyncio.CancelledError:
                pass  # Expected when the bot is stopped
            
            # Verify the initialization chain
            mock_application_class.builder.assert_called_once()
            mock_builder.token.assert_called_with("test_token")
            mock_token_builder.build.assert_called_once()
            
            # Verify bot setup
            assert mock_application.add_handler.call_count == 4  # Should add 4 handlers
            mock_application.initialize.assert_called_once()
            mock_application.start.assert_called_once()
            mock_application.run_polling.assert_called_once()

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

if __name__ == '__main__':
    pytest.main() 