"""
Unit tests for Anthropic and Google Gemini Multi-Provider Client Wrappers
"""

import os
import unittest
from unittest.mock import MagicMock
from costopt import CostOpt


class TestMultiProviderWrappers(unittest.TestCase):
    def setUp(self):
        self.cache_db = "test_multi_provider_cache.db"
        if os.path.exists(self.cache_db):
            try: os.remove(self.cache_db)
            except Exception: pass

    def tearDown(self):
        if os.path.exists(self.cache_db):
            try: os.remove(self.cache_db)
            except Exception: pass

    def test_anthropic_wrapper_detection_and_call(self):
        mock_response = MagicMock()
        mock_response.id = "msg_12345"
        mock_block = MagicMock()
        mock_block.text = "Hello from Anthropic Claude!"
        mock_response.content = [mock_block]
        mock_usage = MagicMock()
        mock_usage.input_tokens = 150
        mock_usage.output_tokens = 40
        mock_response.usage = mock_usage

        mock_messages = MagicMock()
        mock_messages.create.return_value = mock_response

        # Use class spec or provider parameter
        mock_anthropic_client = MagicMock(spec=["messages"])
        mock_anthropic_client.messages = mock_messages

        client = CostOpt(mock_anthropic_client, provider="anthropic", cache_db_path=self.cache_db, telemetry_db_path=":memory:")
        self.assertEqual(client.provider, "anthropic")

        res = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello Claude"}]
        )

        mock_messages.create.assert_called_once()
        self.assertEqual(res.id, "msg_12345")
        self.assertEqual(res.content[0].text, "Hello from Anthropic Claude!")

    def test_anthropic_caching(self):
        mock_response = MagicMock()
        mock_response.id = "msg_cache_test"
        mock_block = MagicMock()
        mock_block.text = "Cached response text"
        mock_response.content = [mock_block]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)

        mock_messages = MagicMock()
        mock_messages.create.return_value = mock_response
        mock_anthropic = MagicMock(spec=["messages"])
        mock_anthropic.messages = mock_messages

        client = CostOpt(mock_anthropic, provider="anthropic", cache_db_path=self.cache_db, telemetry_db_path=":memory:")

        # First call -> Live call
        r1 = client.messages.create(model="claude-3-5-sonnet", messages=[{"role": "user", "content": "Duplicate test"}])
        # Second call -> Cache hit
        r2 = client.messages.create(model="claude-3-5-sonnet", messages=[{"role": "user", "content": "Duplicate test"}])

        self.assertEqual(mock_messages.create.call_count, 1)
        self.assertEqual(r1.content[0].text, r2.content[0].text)

    def test_gemini_wrapper_detection_and_call(self):
        mock_gemini_model = MagicMock(spec=["model_name", "generate_content"])
        mock_gemini_model.model_name = "models/gemini-1.5-pro"
        mock_gem_response = MagicMock()
        mock_gem_response.text = "Hello from Google Gemini Pro!"
        mock_gem_usage = MagicMock(prompt_token_count=120, candidates_token_count=35)
        mock_gem_response.usage_metadata = mock_gem_usage
        mock_gemini_model.generate_content.return_value = mock_gem_response

        model = CostOpt(mock_gemini_model, provider="google", cache_db_path=self.cache_db, telemetry_db_path=":memory:")
        self.assertEqual(model.provider, "google")

        res = model.generate_content("Summarize quantum physics")

        mock_gemini_model.generate_content.assert_called_once_with("Summarize quantum physics")
        self.assertEqual(res.text, "Hello from Google Gemini Pro!")

    def test_gemini_caching(self):
        mock_gemini_model = MagicMock(spec=["model_name", "generate_content"])
        mock_gemini_model.model_name = "models/gemini-1.5-flash"
        mock_response = MagicMock(text="Gemini cached text")
        mock_gemini_model.generate_content.return_value = mock_response

        model = CostOpt(mock_gemini_model, provider="google", cache_db_path=self.cache_db, telemetry_db_path=":memory:")

        # First call -> Live call
        r1 = model.generate_content("Same query")
        # Second call -> Cache hit
        r2 = model.generate_content("Same query")

        self.assertEqual(mock_gemini_model.generate_content.call_count, 1)
        self.assertEqual(r1.text, r2.text)


if __name__ == "__main__":
    unittest.main()
