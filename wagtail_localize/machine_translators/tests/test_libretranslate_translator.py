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

    @mock.patch(
        "wagtail_localize.machine_translators.libretranslate.LibreTranslator.translate",
        return_value={
            StringValue("Hello world!"): StringValue("Bonjour le monde!"),
            StringValue("This is a sentence. This is another sentence."): StringValue(
                "Ceci est une phrase. Ceci est une autre phrase."
            ),
        },
    )
    def test_translate_text(self, mock_translate):
        self.assertIsInstance(self.translator, LibreTranslator)

        translations = self.translator.translate(
            self.english_locale,
            self.french_locale,
            {
                StringValue("Hello world!"),
                StringValue("This is a sentence. This is another sentence."),
            },
        )

        self.assertEqual(
            translations,
            {
                StringValue("Hello world!"): StringValue("Bonjour le monde!"),
                StringValue(
                    "This is a sentence. This is another sentence."
                ): StringValue("Ceci est une phrase. Ceci est une autre phrase."),
            },
        )

    @mock.patch(
        "wagtail_localize.machine_translators.libretranslate.LibreTranslator.translate",
        return_value={
            StringValue('<a id="a1">Hello !</a>. <b>This is a test</b>.'): StringValue(
                """<a id="a1">Bonjour !</a>. <b>C'est un test</b>."""
            ),
        },
    )
    def test_translate_html(self, mock_translate):
        self.assertIsInstance(self.translator, LibreTranslator)

        string, attrs = StringValue.from_source_html(
            '<a href="https://en.wikipedia.org/wiki/World">Hello !</a>. <b>This is a test</b>.'
        )

        translations = self.translator.translate(
            self.english_locale, self.french_locale, [string]
        )

        self.assertEqual(
            translations[string].render_html(attrs),
            """<a href="https://en.wikipedia.org/wiki/World">Bonjour !</a>. <b>C'est un test</b>.""",
        )

    def test_can_translate(self):
        self.assertIsInstance(self.translator, LibreTranslator)

        french_locale = Locale.objects.get(language_code="fr")

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
