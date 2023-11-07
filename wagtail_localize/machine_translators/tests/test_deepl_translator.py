from django.test import TestCase, override_settings

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.machine_translators.deepl import DeepLTranslator, language_code


DEEPL_SETTINGS_FREE_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:fx"},
}

DEEPL_SETTINGS_PAID_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla"},
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
