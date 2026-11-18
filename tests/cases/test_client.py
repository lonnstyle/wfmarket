"""Tests for the Client class header configuration and construction validation."""

from __future__ import annotations

from unittest import mock

import httpx

import wfmarket
import wfmarket.constants as _c
from wfmarket.client import Client

from .base import BaseTest


class TestClientConstructionDefaults(BaseTest):
    """Tests for default Client header values."""

    def test_default_language_is_en(self):
        """Default language should be 'en'."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertEqual(client.language, "en")

    def test_default_platform_is_pc(self):
        """Default platform should be Platform.PC."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertEqual(client.platform, _c.Platform.PC)

    def test_default_crossplay_is_false(self):
        """Default crossplay should be False."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertFalse(client.crossplay)

    def test_default_user_agent(self):
        """Default User-Agent should use the package version."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            expected = f"wfmarket.py/{wfmarket.__version__}"
            self.assertEqual(client.user_agent, expected)

    def test_default_base_url(self):
        """Default base_url should be the Warframe.Market API URL."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertEqual(client.base_url, "https://api.warframe.market")

    def test_headers_contains_all_required_keys(self):
        """Headers dict should contain User-Agent, Language, Platform, Crossplay, Accept."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            headers = client.headers
            for key in ("User-Agent", "Language", "Platform", "Crossplay", "Accept"):
                self.assertIn(key, headers)

    def test_accept_header_is_application_json(self):
        """Accept header should be 'application/json'."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertEqual(client.headers["Accept"], "application/json")

    def test_crossplay_header_is_json_serialized_false(self):
        """Crossplay header should be JSON-serialized 'false'."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            self.assertEqual(client.headers["Crossplay"], "false")


class TestClientConstructionCustomValues(BaseTest):
    """Tests for custom Client header values."""

    def test_custom_language(self):
        """Custom language should be reflected in headers and property."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(language="ja")
            self.assertEqual(client.language, "ja")
            self.assertEqual(client.headers["Language"], "ja")

    def test_custom_platform(self):
        """Custom platform should be reflected in headers and property."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(platform=_c.Platform.XBOX)
            self.assertEqual(client.platform, _c.Platform.XBOX)
            self.assertEqual(client.headers["Platform"], "xbox")

    def test_crossplay_true(self):
        """crossplay=True should set header to 'true' and property to True."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(crossplay=True)
            self.assertTrue(client.crossplay)
            self.assertEqual(client.headers["Crossplay"], "true")

    def test_custom_user_agent(self):
        """Custom User-Agent should override the default."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(user_agent="MyBot/1.0")
            self.assertEqual(client.user_agent, "MyBot/1.0")

    def test_language_constant_works(self):
        """Pre-defined language constants should work as values."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(language="ko")
            self.assertEqual(client.language, "ko")

    def test_platform_enum_member_works(self):
        """Platform enum members should work as values."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(platform=_c.Platform.PS4)
            self.assertEqual(client.platform, _c.Platform.PS4)


class TestClientConstructionValidation(BaseTest):
    """Tests for Client construction-time validation."""

    def test_invalid_language_raises_value_error(self):
        """An unsupported language code should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            Client(language="invalid")
        self.assertIn("Unsupported language", str(ctx.exception))
        self.assertIn("'invalid'", str(ctx.exception))

    def test_none_language_uses_default(self):
        """language=None should fall back to default 'en', not raise."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(language=None)
            self.assertEqual(client.language, "en")

    def test_invalid_platform_raises_value_error(self):
        """An unsupported platform should raise ValueError."""

        # Create a fake Platform-like object that isn't in SUPPORTED_PLATFORMS
        class FakePlatform:
            value = "vr"

        with self.assertRaises(ValueError) as ctx:
            Client(platform=FakePlatform())  # type: ignore[arg-type]
        self.assertIn("Unsupported platform", str(ctx.exception))

    def test_switch_crossplay_raises_value_error(self):
        """Switch + crossplay=True should raise ValueError."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                Client(platform=_c.Platform.SWITCH, crossplay=True)
            self.assertIn("Switch", str(ctx.exception))
            self.assertIn("crossplay", str(ctx.exception).lower())

    def test_switch_crossplay_false_is_ok(self):
        """Switch + crossplay=False (default) should be valid."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(platform=_c.Platform.SWITCH)
            self.assertEqual(client.platform, _c.Platform.SWITCH)
            self.assertFalse(client.crossplay)

    def test_all_languages_accepted(self):
        """Every defined language enum member should be accepted without error."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            for lang in _c.LANGUAGES:
                client = Client(language=lang)
                self.assertEqual(client.language, lang.value)

    def test_language_enum_member_works(self):
        """Language enum members should work directly as values (str mixin)."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client(language=_c.Language.JA)
            self.assertEqual(client.language, "ja")

    def test_language_enum_compares_equal_to_string(self):
        """Language enum members compare equal to their string value."""
        self.assertEqual(_c.Language.KO, "ko")
        self.assertEqual(_c.Language.ZH_HANS, "zh-hans")

    def test_all_platforms_accepted(self):
        """Every Platform enum member should be accepted without error."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            for plat in _c.SUPPORTED_PLATFORMS:
                # Only crossplay-capable platforms can use crossplay=True
                cp = plat in _c.CROSSPLAY_CAPABLE_PLATFORMS
                client = Client(platform=plat, crossplay=cp)
                self.assertEqual(client.platform, plat)


class TestClientHeadersReadOnly(BaseTest):
    """Tests that the headers property returns a copy (not the internal dict)."""

    def test_headers_is_a_copy(self):
        """Modifying the returned dict should not affect the client's headers."""
        with mock.patch.object(httpx.AsyncClient, "__init__", return_value=None):
            client = Client()
            headers_copy = client.headers
            headers_copy["Language"] = "hacked"
            self.assertNotEqual(client.headers["Language"], "hacked")
