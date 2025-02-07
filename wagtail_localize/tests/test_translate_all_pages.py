from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Locale, Page
from wagtail_localize.test.models import TestPage

User = get_user_model()


class TranslateAllPagesCommandTest(TestCase):
    def setUp(self):
        # Set up locales
        self.default_locale = Locale.objects.get(language_code="en")
        Locale.objects.create(language_code="fr")
        Locale.objects.create(language_code="es")
        User.objects.create(is_superuser=True, is_staff=True, username="admin")

        self.page = Page.objects.get(id=2)

    def test_translate_all_pages_dry_run(self):
        # Test dry-run mode to ensure no changes are made
        call_command("translate_all_pages", "en", "--dry-run")

        # Assert no new pages are created
        self.assertEqual(Page.objects.exclude(locale=self.default_locale).count(), 0)

    def test_translate_all_pages_excludes_models(self):
        # Test exclude_models argument
        call_command("translate_all_pages", "en", "--exclude", "Page")

        # Assert the model is excluded from translation
        self.assertEqual(Page.objects.exclude(locale=self.default_locale).count(), 0)

    def test_translate_all_pages_translation_process(self):
        # Test successful translation
        call_command("translate_all_pages", "en")

        # Assert translations are created for target locale
        translated_pages = Page.objects.exclude(locale=self.default_locale)
        self.assertEqual(translated_pages.count(), 2)

    def test_translate_all_pages_dry_run_with_exclude_models(self):
        call_command("translate_all_pages", "en", "--dry-run", "--exclude", "Page")
        self.assertEqual(Page.objects.exclude(locale=self.default_locale).count(), 0)

    def test_translate_all_pages_excludes_multiple_models(self):
        call_command("translate_all_pages", "en", "--exclude", "Page", "TestPage")

        # Assert no translated pages
        self.assertEqual(Page.objects.exclude(locale=self.default_locale).count(), 0)
        self.assertEqual(TestPage.objects.exclude(locale=self.default_locale).count(), 0)

    def test_translate_all_pages_invalid_exclude_model(self):
        out = StringIO()
        err = StringIO()

        call_command('translate_all_pages', 'en', '--exclude', 'InvalidModel', verbosity=3, stdout=out, stderr=err)

        self.assertIn("Model 'InvalidModel' not found in any installed app", err.getvalue())
        self.assertEqual(Page.objects.exclude(locale=self.default_locale).count(), 2)
