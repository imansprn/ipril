import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from main import Bot, UserData

class TestUserData(unittest.TestCase):
    def setUp(self):
        self.user = UserData(123)

    def test_can_make_request(self):
        # Test rate limiting
        self.assertTrue(self.user.can_make_request())
        
        # Add maximum requests
        for _ in range(15):
            self.user.add_request()
        
        # Should be rate limited
        self.assertFalse(self.user.can_make_request())

    def test_add_request(self):
        initial_count = len(self.user.last_requests)
        self.user.add_request()
        self.assertEqual(len(self.user.last_requests), initial_count + 1)

class TestBot(unittest.TestCase):
    def setUp(self):
        self.bot = Bot()
        self.bot.token = "test_token"
        self.bot.api_key = "test_api_key"

    @patch('main.Application')
    def test_run(self, mock_application):
        # Test bot initialization
        self.bot.run()
        mock_application.builder().token.assert_called_with("test_token")

    def test_load_user_data(self):
        # Test loading user data
        self.bot.load_user_data()
        self.assertIsInstance(self.bot.users, dict)

    @patch('aiofiles.open')
    async def test_save_user_data(self, mock_open):
        # Test saving user data
        self.bot.users[123] = UserData(123)
        await self.bot.save_user_data()
        mock_open.assert_called()

    @patch('aiofiles.open')
    async def test_backup_user_data(self, mock_open):
        # Test backup functionality
        await self.bot.backup_user_data()
        mock_open.assert_called()

if __name__ == '__main__':
    unittest.main() 