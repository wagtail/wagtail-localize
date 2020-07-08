from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import translation
from wagtail.core.models import Page

from wagtail_localize.models import Locale
from wagtail_localize.test.models import TestPage, TestHomePage


def make_test_page(**kwargs):
    root_page = Page.objects.get(id=1)
    kwargs.setdefault("title", "Test page")
    return root_page.add_child(instance=TestPage(**kwargs))


class TestLocaleModel(TestCase):
    def setUp(self):
        language_codes = dict(settings.LANGUAGES).keys()

        for language_code in language_codes:
            Locale.objects.update_or_create(
                language_code=language_code, defaults={"is_active": True}
            )

    def test_default(self):
        locale = Locale.objects.default()
        self.assertEqual(locale.language_code, "en")

    @override_settings(LANGUAGE_CODE="fr-ca")
    def test_default_doesnt_have_to_be_english(self):
        locale = Locale.objects.default()
        self.assertEqual(locale.language_code, "fr")

    def test_get_active_default(self):
        self.assertEqual(Locale.get_active().language_code, "en")

    def test_get_active_overridden(self):
        with translation.override("fr"):
            self.assertEqual(Locale.get_active().language_code, "fr")

    def test_get_display_name(self):
        locale = Locale.objects.get(language_code="en")
        self.assertEqual(locale.get_display_name(), "English")

    def test_get_display_name_for_unconfigured_langauge(self):
        # This language is not in LANGUAGES so it should just return the language code
        locale = Locale.objects.create(language_code="foo")
        self.assertIsNone(locale.get_display_name())

    def test_str(self):
        locale = Locale.objects.get(language_code="en")
        self.assertEqual(str(locale), "English")

    def test_str_for_unconfigured_langauge(self):
        # This language is not in LANGUAGES so it should just return the language code
        locale = Locale.objects.create(language_code="foo")
        self.assertEqual(str(locale), "foo")

    def test_get_all_pages(self):
        locale = Locale.objects.get(language_code="en")
        another_locale = Locale.objects.get(language_code="fr")

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
