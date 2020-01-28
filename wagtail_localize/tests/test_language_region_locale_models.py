from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import translation
from wagtail.core.models import Page

from wagtail_localize.models import Language, Region, Locale
from wagtail_localize.test.models import TestPage, TestHomePage


def make_test_page(**kwargs):
    root_page = Page.objects.get(id=1)
    kwargs.setdefault("title", "Test page")
    return root_page.add_child(instance=TestPage(**kwargs))


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

    def test_get_display_name(self):
        language = Language.objects.get(code="en")
        self.assertEqual(language.get_display_name(), "English")

    def test_get_display_name_for_unconfigured_langauge(self):
        # This language is not in LANGUAGES so it should just return the language code
        language = Language.objects.create(code="foo")
        self.assertIsNone(language.get_display_name())

    def test_str(self):
        language = Language.objects.get(code="en")
        self.assertEqual(str(language), "English (en)")

    def test_str_for_unconfigured_langauge(self):
        # This language is not in LANGUAGES so it should just return the language code
        language = Language.objects.create(code="foo")
        self.assertEqual(str(language), "foo")


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

    def test_str(self):
        locale = Locale.objects.get(region__slug="default", language__code="en")
        self.assertEqual(str(locale), "Default / English")

    def test_get_all_pages(self):
        locale = Locale.objects.get(region__slug="default", language__code="en")
        another_locale = Locale.objects.get(region__slug="default", language__code="fr")

        # Create pages in different locales
        home_page = TestHomePage.objects.get()
        page_default_locale = make_test_page(locale=locale)
        page_another_locale = make_test_page(locale=another_locale)

        self.assertEqual(
            list(locale.get_all_pages()),
            [home_page.page_ptr, page_default_locale.page_ptr],
        )
        self.assertEqual(
            list(another_locale.get_all_pages()), [page_another_locale.page_ptr]
        )
