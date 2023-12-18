from django.test import TestCase, override_settings
from wagtail.models import Locale

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.machine_translators.libretranslate import LibreTranslator


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
        self.french_locale = Locale.objects.create(language_code="fr")
        self.translator = get_machine_translator()

    def test_api_endpoint(self):
        self.assertIsInstance(self.translator, LibreTranslator)
        api_endpoint = self.translator.get_api_endpoint()
        self.assertEqual(api_endpoint, "https://libretranslate.org")

    # This probably requires a request to use the API but the test works against my local instance
    # def test_translate_text(self):
    #     self.assertIsInstance(self.translator, LibreTranslator)

    #     translations = self.translator.translate(
    #         self.english_locale,
    #         self.french_locale,
    #         {
    #             StringValue("Hello world!"),
    #             StringValue("This is a sentence. This is another sentence."),
    #         },
    #     )

    #     self.assertEqual(
    #         translations,
    #         {
    #             StringValue("Hello world!"): StringValue("Bonjour !"),
    #             StringValue(
    #                 "This is a sentence. This is another sentence."
    #             ): StringValue("C'est une phrase. C'est une autre phrase."),
    #         },
    #     )

    # This has been commented out because after a while the public API started
    # to return different results for the same input.
    # This probably requires a request to use the API but the test works against my local instance
    # def test_translate_html(self):
    #     self.assertIsInstance(self.translator, LibreTranslator)

    #     string, attrs = StringValue.from_source_html(
    #         '<a href="https://en.wikipedia.org/wiki/World">Hello !</a>. <b>This is a test</b>.'
    #     )

    #     translations = self.translator.translate(
    #         self.english_locale, self.french_locale, [string]
    #     )

    #     self.assertEqual(
    #         translations[string].render_html(attrs),
    #         "Bonjour ! C'est un test enregistré/b.",
    #     )

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
