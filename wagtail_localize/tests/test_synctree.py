from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from wagtail.core.models import Locale, Page

from wagtail_localize.models import LocaleSynchronization
from wagtail_localize.synctree import PageIndex
from wagtail_localize.test.models import TestPage, TestHomePage


class TestPageIndex(TestCase):
    def setUp(self):
        self.en_locale = Locale.objects.get(language_code="en")
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.fr_ca_locale = Locale.objects.create(language_code="fr-CA")
        self.es_locale = Locale.objects.create(language_code="es")

        root_page = Page.objects.get(id=1)
        root_page.get_children().delete()
        root_page.refresh_from_db()
        self.en_homepage = root_page.add_child(instance=TestHomePage(title="Home"))

    def test_from_database(self):
        fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        fr_ca_homepage = fr_homepage.copy_for_translation(self.fr_ca_locale)

        en_aboutpage = self.en_homepage.add_child(
            instance=TestPage(title="About", slug="about",)
        )

        fr_aboutpage = en_aboutpage.copy_for_translation(self.fr_locale)
        fr_aboutpage.copy_for_translation(
            self.fr_ca_locale, alias=True
        )

        fr_ca_homepage.refresh_from_db()
        fr_ca_canadaonlypage = fr_ca_homepage.add_child(
            instance=TestPage(
                title="Only Canada", slug="only-canada", locale=self.fr_ca_locale,
            )
        )

        # Create an index and sort it by tree position
        page_index = PageIndex.from_database().sort_by_tree_position()

        # Homepage should be first
        homepage_entry = page_index.pages[0]
        self.assertEqual(
            homepage_entry.content_type, ContentType.objects.get_for_model(TestHomePage)
        )
        self.assertEqual(homepage_entry.translation_key, self.en_homepage.translation_key)
        self.assertEqual(homepage_entry.source_locale, self.en_locale)
        self.assertIsNone(homepage_entry.parent_translation_key)
        self.assertEqual(
            homepage_entry.locales,
            [self.en_locale.id, self.fr_locale.id, self.fr_ca_locale.id],
        )
        self.assertEqual(homepage_entry.aliased_locales, [])

        aboutpage_entry = page_index.pages[1]
        self.assertEqual(
            aboutpage_entry.content_type, ContentType.objects.get_for_model(TestPage)
        )
        self.assertEqual(aboutpage_entry.translation_key, en_aboutpage.translation_key)
        self.assertEqual(aboutpage_entry.source_locale, self.en_locale)
        self.assertEqual(
            aboutpage_entry.parent_translation_key, homepage_entry.translation_key
        )
        self.assertEqual(
            aboutpage_entry.locales, [self.en_locale.id, self.fr_locale.id]
        )
        self.assertEqual(
            aboutpage_entry.aliased_locales, [self.fr_ca_locale.id]
        )

        canadaonlypage_entry = page_index.pages[2]
        self.assertEqual(
            canadaonlypage_entry.content_type,
            ContentType.objects.get_for_model(TestPage),
        )
        self.assertEqual(
            canadaonlypage_entry.translation_key, fr_ca_canadaonlypage.translation_key
        )
        self.assertEqual(canadaonlypage_entry.source_locale, self.fr_ca_locale)
        self.assertEqual(
            canadaonlypage_entry.parent_translation_key, homepage_entry.translation_key
        )
        self.assertEqual(canadaonlypage_entry.locales, [self.fr_ca_locale.id])
        self.assertEqual(canadaonlypage_entry.aliased_locales, [])


class TestSignals(TestCase):
    def setUp(self):
        self.en_locale = Locale.objects.get(language_code="en")
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.fr_ca_locale = Locale.objects.create(language_code="fr-CA")
        self.es_locale = Locale.objects.create(language_code="es")

        root_page = Page.objects.get(id=1)
        root_page.get_children().delete()
        root_page.refresh_from_db()

        self.en_homepage = root_page.add_child(instance=TestHomePage(title="Home"))
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.fr_ca_homepage = self.fr_homepage.copy_for_translation(self.fr_ca_locale)

        self.en_aboutpage = self.en_homepage.add_child(
            instance=TestPage(title="About", slug="about",)
        )

        self.fr_aboutpage = self.en_aboutpage.copy_for_translation(self.fr_locale)

        self.fr_ca_homepage.refresh_from_db()
        self.fr_ca_canadaonlypage = self.fr_ca_homepage.add_child(
            instance=TestPage(
                title="Only Canada", slug="only-canada", locale=self.fr_ca_locale,
            )
        )

        LocaleSynchronization.objects.create(
            locale=self.fr_locale,
            sync_from=self.en_locale,
        )

        LocaleSynchronization.objects.create(
            locale=self.fr_ca_locale,
            sync_from=self.fr_locale,
        )

    def test_create_new_page(self):
        LocaleSynchronization.objects.create(
            locale=self.es_locale,
            sync_from=self.en_locale,
        )

        new_page = self.en_homepage.add_child(
            instance=TestPage(title="Foo", slug="foo")
        )

        # Check it created aliases for the other locales
        fr_new_page = TestPage.objects.get(
            translation_key=new_page.translation_key,
            locale=self.fr_locale,
            alias_of=new_page,
        )
        self.assertFalse(fr_new_page.revisions.exists())

        fr_ca_new_page = TestPage.objects.get(
            translation_key=new_page.translation_key,
            locale=self.fr_ca_locale,
            alias_of=fr_new_page,
        )
        self.assertFalse(fr_ca_new_page.revisions.exists())

        # Should've also created parent for this one
        es_new_page = TestPage.objects.get(
            translation_key=new_page.translation_key,
            locale=self.es_locale,
            alias_of=new_page,
        )
        self.assertFalse(es_new_page.revisions.exists())

    def test_create_new_locale_synchronisation(self):
        new_page = self.en_homepage.add_child(
            instance=TestPage(title="Foo", slug="foo")
        )

        # Spanish version shouldn't exist yet
        self.assertFalse(TestPage.objects.filter(translation_key=new_page.translation_key, locale=self.es_locale).exists())

        # Creating the locale synchronisation should create the page in Spanish
        LocaleSynchronization.objects.create(
            locale=self.es_locale,
            sync_from=self.en_locale,
        )

        es_new_page = TestPage.objects.get(translation_key=new_page.translation_key, locale=self.es_locale)
        self.assertEqual(es_new_page.alias_of, new_page.page_ptr)
