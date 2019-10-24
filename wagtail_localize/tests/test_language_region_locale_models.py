from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import translation

from wagtail_localize.models import Language, Region, Locale


class TestLanguageModel(TestCase):
    def setUp(self):
        language_codes = dict(settings.LANGUAGES).keys()

        for language_code in language_codes:
            Language.objects.update_or_create(
                code=language_code, defaults={"is_active": True}
            )

    def test_default(self):
        default_language = Language.objects.default()
        self.assertEqual(default_language.code, "en")
        self.assertEqual(Language.objects.default_id(), default_language.id)

    @override_settings(LANGUAGE_CODE="fr-ca")
    def test_default_doesnt_have_to_be_english(self):
        default_language = Language.objects.default()
        self.assertEqual(default_language.code, "fr")
        self.assertEqual(Language.objects.default_id(), default_language.id)

    def test_get_active_default(self):
        self.assertEqual(Language.get_active().code, "en")

    def test_get_active_overridden(self):
        with translation.override("fr"):
            self.assertEqual(Language.get_active().code, "fr")

    def test_as_rfc5646_language_tag(self):
        tests = [("en", "en"), ("en-gb", "en-GB"), ("zh-hans", "zh-Hans")]

        for code, expected in tests:
            with self.subTest(code=code):
                result = Language(code=code).as_rfc5646_language_tag()
                self.assertEqual(result, expected)

    def test_get_by_rfc5646_language_tag(self):
        language = Language.objects.create(code="en-gb")

        got_language = Language.get_by_rfc5646_language_tag("en-GB")

        self.assertEqual(language, got_language)

    def test_get_display_name(self):
        language = Language.objects.get(code="en")
        self.assertEqual(language.get_display_name(), "English")

    def test_str(self):
        language = Language.objects.get(code="en")
        self.assertEqual(str(language), "English (en)")


class TestRegionModel(TestCase):
    def test_default(self):
        region = Region.objects.default()
        self.assertEqual(region.name, "Default")
        self.assertEqual(region.slug, "default")
        self.assertTrue(region.is_default)


class TestLocaleModel(TestCase):
    def setUp(self):
        language_codes = dict(settings.LANGUAGES).keys()

        for language_code in language_codes:
            Language.objects.update_or_create(
                code=language_code, defaults={"is_active": True}
            )

    def test_default(self):
        locale = Locale.objects.default()
        self.assertEqual(locale.region.name, "Default")
        self.assertEqual(locale.language.code, "en")

    @override_settings(LANGUAGE_CODE="fr-ca")
    def test_default_doesnt_have_to_be_english(self):
        locale = Locale.objects.default()
        self.assertEqual(locale.region.name, "Default")
        self.assertEqual(locale.language.code, "fr")

    def test_slug_default_region(self):
        locale = Locale.objects.get(region__slug="default", language__code="en")
        self.assertEqual(locale.slug, "en")

    def test_slug_other_region(self):
        region = Region.objects.create(name="European Union", slug="eu")
        region.languages.set(
            [Language.objects.get(code="en"), Language.objects.get(code="fr")]
        )

        locale = Locale.objects.get(region=region, language__code="en")
        self.assertEqual(locale.slug, "eu-en")

    def test_str(self):
        locale = Locale.objects.get(region__slug="default", language__code="en")
        self.assertEqual(str(locale), "Default / English")
