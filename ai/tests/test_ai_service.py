import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from ai_service import ask_ai


class AskAiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            "os.environ",
            {
                "AI_API_KEY": "test-key",
                "AI_BASE_URL": "https://example.test/v1",
                "AI_MODEL": "test-model",
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_sends_chat_request_and_returns_answer(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Namaste!"}}]}
        ).encode()

        with patch("ai_service.urllib.request.urlopen", return_value=response) as urlopen:
            answer = ask_ai("hello", [{"role": "user", "content": "hi"}])

        self.assertEqual(answer, "Namaste!")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.test/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"][-2:], [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "hello"},
        ])
        self.assertEqual(payload["messages"][0]["role"], "system")

    def test_missing_api_key_does_not_make_network_request(self) -> None:
        with patch.dict("os.environ", {"AI_API_KEY": ""}), patch(
            "ai_service.urllib.request.urlopen"
        ) as urlopen:
            answer = ask_ai("hello", [])

        self.assertIn("AI_API_KEY", answer)
        urlopen.assert_not_called()

    def test_reports_http_error_without_exposing_credentials(self) -> None:
        error = HTTPError(
            "https://example.test/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            None,
        )
        with patch("ai_service.urllib.request.urlopen", side_effect=error):
            answer = ask_ai("hello", [])

        self.assertIn("HTTP 401", answer)
        self.assertNotIn("test-key", answer)

    def test_reports_connection_error(self) -> None:
        with patch(
            "ai_service.urllib.request.urlopen",
            side_effect=URLError("offline"),
        ):
            answer = ask_ai("hello", [])

        self.assertIn("connect nahi hua", answer)
        self.assertIn("offline", answer)

    def test_rejects_malformed_provider_response(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"not json"

        with patch("ai_service.urllib.request.urlopen", return_value=response):
            answer = ask_ai("hello", [])

        self.assertIn("response samajh nahi aaya", answer)

    def test_rejects_incomplete_configuration(self) -> None:
        with patch.dict("os.environ", {"AI_BASE_URL": "file:///tmp"}):
            answer = ask_ai("hello", [])

        self.assertIn("configuration invalid", answer)


if __name__ == "__main__":
    unittest.main()
