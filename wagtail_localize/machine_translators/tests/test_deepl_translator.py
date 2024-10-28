from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.machine_translators.deepl import DeepLTranslator, language_code
from wagtail_localize.strings import StringValue


DEEPL_SETTINGS_FREE_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:fx"},
}

DEEPL_SETTINGS_PAID_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla"},
}

DEEPL_SETTINGS_WITH_FORMALITY = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {
        "AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla",
        "FORMALITY": "prefer_less",
    },
}

DEEPL_SETTINGS_WITH_UNSUPPORTED_FORMALITY = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {
        "AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla",
        "FORMALITY": "less",
    },
}

DEEPL_SETTINGS_WITH_GLOSSARY_IDS = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {
        "AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla",
        "GLOSSARY_IDS": {
            ("EN", "DE"): "test-id-de",
            ("EN", "FR"): "test-id-fr",
        },
    },
}

DEEPL_SETTINGS_WITH_MISSING_GLOSSARY_IDS = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {
        "AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla",
        "GLOSSARY_IDS": {
            ("EN", "FR"): "test-id-fr",
            ("EN", "DE"): "test-id-de",
        },
    },
}


class TestDeeplTranslator(TestCase):
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_FREE_ENDPOINT)
    def test_free_api_endpoint(self):
        translator = get_machine_translator()
        self.assertIsInstance(translator, DeepLTranslator)
        free_api_endpoint = translator.get_api_endpoint()
        self.assertEqual(free_api_endpoint, "https://api-free.deepl.com/v2/translate")

    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_PAID_ENDPOINT)
    def test_paid_api_endpoint(self):
        translator = get_machine_translator()
        self.assertIsInstance(translator, DeepLTranslator)
        paid_api_endpoint = translator.get_api_endpoint()
        self.assertEqual(paid_api_endpoint, "https://api.deepl.com/v2/translate")

    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_WITH_FORMALITY)
    @patch("requests.post")
    def test_translate_with_formality_option(self, mock_post):
        translator = get_machine_translator()
        source_locale = Mock(language_code="en")
        target_locale = Mock(language_code="de")
        strings = [StringValue("Test string")]

        translator.translate(source_locale, target_locale, strings)

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertIn("formality", called_args[1])
        self.assertEqual(called_args[1]["formality"], "prefer_less")

    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_PAID_ENDPOINT)
    @patch("requests.post")
    def test_translate_without_formality_option(self, mock_post):
        translator = get_machine_translator()
        source_locale = Mock(language_code="en")
        target_locale = Mock(language_code="de")
        strings = [StringValue("Test string")]

        translator.translate(source_locale, target_locale, strings)

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertNotIn("formality", called_args[1])

    @override_settings(
        WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_WITH_UNSUPPORTED_FORMALITY
    )
    @patch("requests.post")
    @patch("warnings.warn")
    def test_translate_with_non_supported_formality_option(self, mock_warn, mock_post):
        translator = get_machine_translator()
        source_locale = Mock(language_code="en")
        target_locale = Mock(language_code="de")
        strings = [StringValue("Test string")]

        translator.translate(source_locale, target_locale, strings)

        mock_warn.assert_called_once()

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertNotIn("formality", called_args[1])

    def test_language_code_as_source(self):
        mapping = {
            "pt-pt": "PT",
            "pt-br": "PT",
            "en-us": "EN",
            "en-gb": "EN",
            "es-es": "ES",
        }
        for code, expected_value in mapping.items():
            with self.subTest(f"Testing language_code with {code}"):
                self.assertEqual(expected_value, language_code(code, is_target=False))

    def test_language_code_as_target(self):
        mapping = {
            "pt-pt": "PT-PT",
            "pt-br": "PT-BR",
            "en-us": "EN-US",
            "en-gb": "EN-GB",
            "es-es": "ES",
        }
        for code, expected_value in mapping.items():
            with self.subTest(f"Testing language_code with {code} as target"):
                self.assertEqual(expected_value, language_code(code, is_target=True))

    @override_settings(
        WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_WITH_GLOSSARY_IDS
    )
    @patch("requests.post")
    def test_translate_with_glossary_ids(self, mock_post):
        translator = get_machine_translator()
        source_locale = Mock(language_code="en")
        target_locale = Mock(language_code="de")
        strings = [StringValue("Test string")]

        translator.translate(source_locale, target_locale, strings)

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertIn("glossary_id", called_args[1])
        self.assertEqual(called_args[1]["glossary_id"], "test-id-de")

    @override_settings(
        WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_WITH_MISSING_GLOSSARY_IDS
    )
    @patch("requests.post")
    def test_translate_with_missing_glossary_ids(self, mock_post):
        translator = get_machine_translator()
        source_locale = Mock(language_code="en")
        target_locale = Mock(language_code="es")
        strings = [StringValue("Test string")]

        translator.translate(source_locale, target_locale, strings)

        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertNotIn("glossary_id", called_args[1])
