from django.test import TestCase

from wagtail_localize.models import Region, Language, Locale


class TestSignals(TestCase):
    # add_new_languages_to_default_region

    def test_add_new_languages_to_default_region(self):
        default_region = Region.objects.default()
        another_region = Region.objects.create(name="United Kingdom", slug="uk")

        language = Language.objects.create(code="fr")

        self.assertTrue(
            Locale.objects.filter(region=default_region, language=language).exists()
        )
        self.assertFalse(
            Locale.objects.filter(region=another_region, language=language).exists()
        )

    def test_add_new_languages_to_default_region__when_no_default_region(self):
        # Remove default region
        Region.objects.all().update(is_default=False)
        region = Region.objects.get()

        language = Language.objects.create(code="fr")

        self.assertFalse(
            Locale.objects.filter(region=region, language=language).exists()
        )

    # update_locales_on_language_change

    def test_update_locales_on_language_change__activate_language(self):
        language = Language.objects.create(code="fr", is_active=False)
        locale = Locale.objects.get(language=language, region=Region.objects.default())

        self.assertFalse(locale.is_active)

        language.is_active = True
        language.save()

        locale.refresh_from_db()

        self.assertTrue(locale.is_active)

    def test_update_locales_on_language_change__deactivate_language(self):
        language = Language.objects.create(code="fr", is_active=True)
        locale = Locale.objects.get(language=language, region=Region.objects.default())

        self.assertTrue(locale.is_active)

        language.is_active = False
        language.save()

        locale.refresh_from_db()

        self.assertFalse(locale.is_active)

    # update_locales_on_region_change

    def test_update_locales_on_region_change__activate_region(self):
        language = Language.objects.get(code="en")
        region = Region.objects.create(
            name="United Kingdom", slug="uk", is_active=False
        )
        region.languages.add(language)
        locale = Locale.objects.get(region=region, language=language)

        self.assertFalse(locale.is_active)

        region.is_active = True
        region.save()

        locale.refresh_from_db()

        self.assertTrue(locale.is_active)

    def test_update_locales_on_region_change__deactivate_region(self):
        language = Language.objects.get(code="en")
        region = Region.objects.create(name="United Kingdom", slug="uk", is_active=True)
        region.languages.add(language)
        locale = Locale.objects.get(region=region, language=language)

        self.assertTrue(locale.is_active)

        region.is_active = False
        region.save()

        locale.refresh_from_db()

        self.assertFalse(locale.is_active)

    def test_update_locales_on_region_languages_change(self):
        region = Region.objects.create(name="United Kingdom", slug="uk", is_active=True)
        language = Language.objects.get(code="en")

        # Locale shouldn't exist yet
        self.assertFalse(
            Locale.objects.filter(region=region, language=language).exists()
        )

        # Add language
        region.languages.add(language)

        # Check locale was created
        locale = Locale.objects.get(region=region, language=language)
        self.assertTrue(locale.is_active)

        # Remove the language
        region.languages.remove(language)

        # Check locale was deactivated
        locale.refresh_from_db()
        self.assertFalse(locale.is_active)

    # TODO update_synchronised_pages_on_publish
