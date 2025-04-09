import unittest
from unittest.mock import patch, MagicMock
from src.services.llm_service import call_llm

class TestLLMService(unittest.TestCase):

    @patch('src.services.llm_service.requests.post')
    def test_call_llm_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "This is a test response."
        }
        mock_post.return_value = mock_response

        prompt = "Test prompt"
        api_key = "test_api_key"
        result = call_llm(prompt, api_key)

        self.assertEqual(result, "This is a test response.")
        mock_post.assert_called_once()

    @patch('src.services.llm_service.requests.post')
    def test_call_llm_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": ""
        }
        mock_post.return_value = mock_response

        prompt = "Test prompt"
        api_key = "test_api_key"
        result = call_llm(prompt, api_key)

        self.assertIsNone(result)
        mock_post.assert_called_once()

    @patch('src.services.llm_service.requests.post')
    def test_call_llm_exception(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        prompt = "Test prompt"
        api_key = "test_api_key"
        result = call_llm(prompt, api_key)

        self.assertIsNone(result)
        mock_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()