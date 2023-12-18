import json

from unittest import mock

from django.test import TestCase, override_settings
from wagtail.models import Locale

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.machine_translators.libretranslate import LibreTranslator
from wagtail_localize.strings import StringValue


LIBRETRANSLATE_SETTINGS_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.libretranslate.LibreTranslator",
    "OPTIONS": {
        "LIBRETRANSLATE_URL": "https://libretranslate.org",
        "API_KEY": "test-api-key",
    },
}


class TestLibreTranslator(TestCase):
    @override_settings(
        WAGTAILLOCALIZE_MACHINE_TRANSLATOR=LIBRETRANSLATE_SETTINGS_ENDPOINT
    )
    def setUp(self):
        self.english_locale = Locale.objects.get()
        self.french_locale = Locale.objects.create(language_code="fr-fr")
        self.translator = get_machine_translator()

    def test_api_endpoint(self):
        self.assertIsInstance(self.translator, LibreTranslator)
        api_endpoint = self.translator.get_api_endpoint()
        self.assertEqual(api_endpoint, "https://libretranslate.org")

    def test_language_code(self):
        self.assertEqual(
            self.translator.language_code(self.english_locale.language_code), "en"
        )
        self.assertEqual(
            self.translator.language_code(self.french_locale.language_code), "fr"
        )
        self.assertEqual(self.translator.language_code("foo-bar-baz"), "foo")

    @mock.patch("wagtail_localize.machine_translators.libretranslate.requests.post")
    def test_translate_text(self, mock_post):
        # Mock the response of requests.post
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "translatedText": [
                "Bonjour le monde!",
                "Ceci est une phrase. Ceci est une autre phrase.",
            ]
        }
        mock_response.raise_for_status = mock.Mock()
        mock_post.return_value = mock_response

        input_strings = [
            StringValue("Hello world!"),
            StringValue("This is a sentence. This is another sentence."),
        ]

        translations = self.translator.translate(
            self.english_locale, self.french_locale, input_strings
        )

        expected_translations = {
            StringValue("Hello world!"): StringValue("Bonjour le monde!"),
            StringValue("This is a sentence. This is another sentence."): StringValue(
                "Ceci est une phrase. Ceci est une autre phrase."
            ),
        }

        # Assertions to check if the translation is as expected
        self.assertEqual(translations, expected_translations)

        # Assert that requests.post was called with the correct arguments
        mock_post.assert_called_once_with(
            LIBRETRANSLATE_SETTINGS_ENDPOINT["OPTIONS"]["LIBRETRANSLATE_URL"]
            + "/translate",
            data=json.dumps(
                {
                    "q": [
                        "Hello world!",
                        "This is a sentence. This is another sentence.",
                    ],
                    "source": "en",
                    "target": "fr",
                    "api_key": LIBRETRANSLATE_SETTINGS_ENDPOINT["OPTIONS"]["API_KEY"],
                }
            ),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    @mock.patch("wagtail_localize.machine_translators.libretranslate.requests.post")
    def test_translate_html(self, mock_post):
        # Mock the response of requests.post
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "translatedText": ["""<a id="a1">Bonjour !</a>. <b>C'est un test</b>."""]
        }
        mock_response.raise_for_status = mock.Mock()
        mock_post.return_value = mock_response

        input_string, attrs = StringValue.from_source_html(
            '<a href="https://en.wikipedia.org/wiki/World">Hello !</a>. <b>This is a test</b>.'
        )

        translations = self.translator.translate(
            self.english_locale, self.french_locale, [input_string]
        )

        expected_translation = {
            input_string: StringValue(
                """<a id="a1">Bonjour !</a>. <b>C'est un test</b>."""
            )
        }

        # Assertions to check if the translation is as expected
        self.assertEqual(translations, expected_translation)

        # Additional assertion to check the rendered HTML
        translated_string = translations[input_string]
        rendered_html = translated_string.render_html(attrs)
        expected_rendered_html = '<a href="https://en.wikipedia.org/wiki/World">Bonjour !</a>. <b>C\'est un test</b>.'

        self.assertEqual(rendered_html, expected_rendered_html)

        # Assert that requests.post was called with the correct arguments
        mock_post.assert_called_once_with(
            LIBRETRANSLATE_SETTINGS_ENDPOINT["OPTIONS"]["LIBRETRANSLATE_URL"]
            + "/translate",
            data=json.dumps(
                {
                    "q": [
                        '<a id="a1">Hello !</a>. <b>This is a test</b>.'
                    ],  # Use the string from StringValue
                    "source": "en",
                    "target": "fr",
                    "api_key": LIBRETRANSLATE_SETTINGS_ENDPOINT["OPTIONS"]["API_KEY"],
                }
            ),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    def test_can_translate(self):
        self.assertIsInstance(self.translator, LibreTranslator)

        french_locale = Locale.objects.create(language_code="fr")

        self.assertTrue(
            self.translator.can_translate(self.english_locale, self.french_locale)
        )
        self.assertTrue(
            self.translator.can_translate(self.english_locale, french_locale)
        )

        # Can't translate the same language
        self.assertFalse(
            self.translator.can_translate(self.english_locale, self.english_locale)
        )

        # Can't translate two variants of the same language
        self.assertFalse(
            self.translator.can_translate(self.french_locale, french_locale)
        )
