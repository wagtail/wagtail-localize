from django.test import TestCase, override_settings

from wagtail_localize.utils import get_language_fallbacks


class TestGetLanguageFallbacks(TestCase):
    @override_settings(
        LANGUAGE_CODE="en-gb", LANGUAGES=[("en", "English"), ("fr", "French")]
    )
    def test_basic(self):
        self.assertEqual(get_language_fallbacks("en"), [])
        self.assertEqual(get_language_fallbacks("fr"), ["en"])
        self.assertEqual(get_language_fallbacks("fr-ca"), ["fr", "en"])

    @override_settings(
        LANGUAGE_CODE="fr", LANGUAGES=[("en", "English"), ("fr", "French")]
    )
    def test_french_default_language(self):
        self.assertEqual(get_language_fallbacks("en"), ["fr"])
        self.assertEqual(get_language_fallbacks("fr"), [])
        self.assertEqual(get_language_fallbacks("fr-ca"), ["fr"])

    @override_settings(
        LANGUAGE_CODE="en",
        LANGUAGES=[
            ("en", "English"),
            ("fr", "French"),
            ("fr-ca", "French (Canada)"),
            ("fr-be", "French (Belguim)"),
        ],
    )
    def test_other_regions_available(self):
        self.assertEqual(get_language_fallbacks("en"), [])
        self.assertEqual(get_language_fallbacks("fr"), ["fr-ca", "fr-be", "en"])
        self.assertEqual(get_language_fallbacks("fr-ca"), ["fr", "fr-be", "en"])

    @override_settings(
        LANGUAGE_CODE="en",
        LANGUAGES=[
            ("en", "English"),
            ("zh", "Chinese"),
            ("zn-cn", "Chinese (China)"),
            ("zh-hant", "Traditional Chinese"),
            ("zh-hans", "Simplified Chinese"),
        ],
    )
    def test_special_cases(self):
        self.assertEqual(get_language_fallbacks("zh"), ["zh-hant", "zh-hans", "en"])
        self.assertEqual(
            get_language_fallbacks("zh-cn"), ["zh-hans", "zh", "zh-hant", "en"]
        )
        self.assertEqual(
            get_language_fallbacks("zh-hk"), ["zh-hant", "zh", "zh-hans", "en"]
        )
