import base64
import unittest
from unittest.mock import patch

from app import auth


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.credentials = patch.multiple(
            auth,
            AUTH_ENABLED=True,
            WEB_USERNAME="dashboard",
            WEB_PASSWORD="a-long-test-password",
            ROKU_API_KEY="a" * 64,
        )
        self.credentials.start()
        self.addCleanup(self.credentials.stop)

    def _basic(self, username: str, password: str) -> str:
        value = base64.b64encode(f"{username}:{password}".encode()).decode()
        return f"Basic {value}"

    def test_accepts_valid_basic_credentials(self):
        self.assertTrue(auth._valid_basic_auth(self._basic("dashboard", "a-long-test-password")))

    def test_rejects_invalid_basic_credentials(self):
        self.assertFalse(auth._valid_basic_auth(self._basic("dashboard", "wrong-password")))
        self.assertFalse(auth._valid_basic_auth("Bearer token"))
        self.assertFalse(auth._valid_basic_auth("Basic not-base64"))

    def test_accepts_only_the_configured_roku_key(self):
        self.assertTrue(auth._valid_roku_key("a" * 64))
        self.assertFalse(auth._valid_roku_key("b" * 64))
        self.assertFalse(auth._valid_roku_key(None))

    def test_validates_minimum_secret_lengths(self):
        auth.validate_auth_config()

        with patch.object(auth, "ROKU_API_KEY", "short"):
            with self.assertRaisesRegex(RuntimeError, "ROKU_API_KEY"):
                auth.validate_auth_config()


if __name__ == "__main__":
    unittest.main()
