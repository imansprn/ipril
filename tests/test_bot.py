import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from main import Bot, UserData

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
        with patch('main.Application') as mock_application:
            # Test bot initialization
            await bot.run()
            mock_application.builder().token.assert_called_with("test_token")

    def test_load_user_data(self, bot):
        # Test loading user data
        bot.load_user_data()
        assert isinstance(bot.users, dict)

    @pytest.mark.asyncio
    async def test_save_user_data(self, bot):
        with patch('aiofiles.open') as mock_open:
            # Test saving user data
            bot.users[123] = UserData(123)
            await bot.save_user_data()
            mock_open.assert_called()

    @pytest.mark.asyncio
    async def test_backup_user_data(self, bot):
        with patch('aiofiles.open') as mock_open:
            # Test backup functionality
            await bot.backup_user_data()
            mock_open.assert_called()

if __name__ == '__main__':
    pytest.main() 