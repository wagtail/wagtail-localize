from django.test import TestCase
from wagtail.core.models import Locale

from wagtail_localize.machine_translators.dummy import DummyTranslator
from wagtail_localize.strings import StringValue


class TestDummyTranslator(TestCase):
    def setUp(self):
        self.english_locale = Locale.objects.get()
        self.french_locale = Locale.objects.create(language_code="fr")

    def test_translate_text(self):
        translations = DummyTranslator({}).translate(self.english_locale, self.french_locale, [
            StringValue("Hello world!"),
            StringValue("This is a sentence. This is another sentence."),
        ])

        self.assertEqual(translations, {
            StringValue("Hello world!"): StringValue("world! Hello"),
            StringValue("This is a sentence. This is another sentence."): StringValue("sentence. another is This sentence. a is This"),
        })

    def test_translate_html(self):
        string, attrs = StringValue.from_source_html('<a href="https://en.wikipedia.org/wiki/World">Hello world!</a>. <b>This is a test</b>.')

        translations = DummyTranslator({}).translate(self.english_locale, self.french_locale, [
            string
        ])

        self.assertEqual(translations[string].render_html(attrs), '.<b>test a is This</b>. <a href="https://en.wikipedia.org/wiki/World">world! Hello</a>')

    def test_can_translate(self):
        canada_french_locale = Locale.objects.create(language_code="fr-CA")

        self.assertTrue(DummyTranslator({}).can_translate(self.english_locale, self.french_locale))
        self.assertTrue(DummyTranslator({}).can_translate(self.english_locale, canada_french_locale))

        # Can't translate the same language
        self.assertFalse(DummyTranslator({}).can_translate(self.english_locale, self.english_locale))

        # Can't translate two variants of the same language
        self.assertFalse(DummyTranslator({}).can_translate(self.french_locale, canada_french_locale))
