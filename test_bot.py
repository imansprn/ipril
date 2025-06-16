import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from bot import UserData, Bot

class TestUserData(unittest.TestCase):
    def setUp(self):
        self.user = UserData(123)

    def test_add_message_with_timestamp(self):
        """Test that new messages are added with timestamps"""
        self.user.add_user_message("hello")
        self.user.add_assistant_message("hi")
        
        # Check that messages have timestamps
        self.assertIn("timestamp", self.user.message_history[0])
        self.assertIn("timestamp", self.user.message_history[1])
        
        # Check that timestamps are datetime objects
        self.assertIsInstance(self.user.message_history[0]["timestamp"], datetime)
        self.assertIsInstance(self.user.message_history[1]["timestamp"], datetime)

    def test_message_history_trim(self):
        """Test that message history is properly trimmed"""
        # Add 12 messages (should be trimmed to 10)
        for i in range(6):
            self.user.add_user_message(f"user message {i}")
            self.user.add_assistant_message(f"assistant message {i}")
        
        self.assertEqual(len(self.user.message_history), 10)
        # Check that oldest messages are removed
        self.assertEqual(self.user.message_history[0]["content"], "user message 1")
        self.assertEqual(self.user.message_history[1]["content"], "assistant message 1")

class TestBot(unittest.TestCase):
    def setUp(self):
        self.bot = Bot()
        self.user = UserData(123)
        # Add some test messages
        self.user.add_user_message("old message 1")
        self.user.add_assistant_message("old response 1")
        self.user.add_user_message("old message 2")
        self.user.add_assistant_message("old response 2")

    @patch('bot.aiohttp.ClientSession')
    async def test_call_deepseek_api_with_old_messages(self, mock_session):
        """Test that old messages without timestamps are included"""
        # Mock the API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "test response"}}]
        })
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        # Call the API
        response = await self.bot.call_deepseek_api(self.user)
        
        # Get the messages sent to the API
        api_call = mock_session.return_value.__aenter__.return_value.post.call_args
        messages = api_call[1]['json']['messages']
        
        # Check that all old messages are included
        self.assertEqual(len(messages), 5)  # 4 messages + 1 system message
        self.assertEqual(messages[1]["content"], "old message 1")
        self.assertEqual(messages[2]["content"], "old response 1")
        self.assertEqual(messages[3]["content"], "old message 2")
        self.assertEqual(messages[4]["content"], "old response 2")

    @patch('bot.aiohttp.ClientSession')
    async def test_call_deepseek_api_with_expired_messages(self, mock_session):
        """Test that messages older than 24 hours are excluded"""
        # Add a message with old timestamp
        old_time = datetime.now() - timedelta(hours=25)
        self.user.message_history.append({
            "role": "user",
            "content": "expired message",
            "timestamp": old_time
        })
        
        # Add a recent message
        self.user.add_user_message("recent message")
        
        # Mock the API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "test response"}}]
        })
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response

        # Call the API
        response = await self.bot.call_deepseek_api(self.user)
        
        # Get the messages sent to the API
        api_call = mock_session.return_value.__aenter__.return_value.post.call_args
        messages = api_call[1]['json']['messages']
        
        # Check that expired message is excluded but recent message is included
        message_contents = [msg["content"] for msg in messages]
        self.assertNotIn("expired message", message_contents)
        self.assertIn("recent message", message_contents)

    @patch('bot.aiohttp.ClientSession')
    async def test_call_deepseek_api_with_all_expired_messages(self, mock_session):
        """Test that all messages are cleared when the last message is expired"""
        # Clear existing messages
        self.user.message_history = []
        
        # Add only expired messages
        old_time = datetime.now() - timedelta(hours=25)
        self.user.message_history.append({
            "role": "user",
            "content": "expired message",
            "timestamp": old_time
        })
        
        # Call the API
        response = await self.bot.call_deepseek_api(self.user)
        
        # Check that history is cleared and appropriate message is returned
        self.assertEqual(len(self.user.message_history), 0)
        self.assertEqual(response, "Your previous conversation has expired. Please start a new conversation.")

if __name__ == '__main__':
    unittest.main() 