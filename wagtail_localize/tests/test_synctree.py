from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Locale, Page
from wagtail.test.utils import WagtailTestUtils

from wagtail_localize.models import LocaleSynchronization
from wagtail_localize.synctree import PageIndex
from wagtail_localize.test.models import TestHomePage, TestPage


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
            instance=TestPage(
                title="About",
                slug="about",
            )
        )

        fr_aboutpage = en_aboutpage.copy_for_translation(self.fr_locale)
        fr_aboutpage.copy_for_translation(self.fr_ca_locale, alias=True)

        fr_ca_homepage.refresh_from_db()
        fr_ca_canadaonlypage = fr_ca_homepage.add_child(
            instance=TestPage(
                title="Only Canada",
                slug="only-canada",
                locale=self.fr_ca_locale,
            )
        )

        # Create an index and sort it by tree position
        page_index = PageIndex.from_database().sort_by_tree_position()

        # Homepage should be first
        homepage_entry = page_index.pages[0]
        self.assertEqual(
            homepage_entry.content_type, ContentType.objects.get_for_model(TestHomePage)
        )
        self.assertEqual(
            homepage_entry.translation_key, self.en_homepage.translation_key
        )
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
        self.assertEqual(aboutpage_entry.aliased_locales, [self.fr_ca_locale.id])

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


class TestSignalsAndHooks(TestCase, WagtailTestUtils):
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
            instance=TestPage(
                title="About",
                slug="about",
            )
        )

        self.fr_aboutpage = self.en_aboutpage.copy_for_translation(self.fr_locale)

        self.fr_ca_homepage.refresh_from_db()
        self.fr_ca_canadaonlypage = self.fr_ca_homepage.add_child(
            instance=TestPage(
                title="Only Canada",
                slug="only-canada",
                locale=self.fr_ca_locale,
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

        # Login
        self.user = self.login()

    def test_create_new_page(self):
        LocaleSynchronization.objects.create(
            locale=self.es_locale,
            sync_from=self.en_locale,
        )

        post_data = {
            "title": "Foo",
            "slug": "foo",
            "action-publish": "publish",
            "test_streamfield-count": "0",
            "test_synchronized_streamfield-count": "0",
            "comments-TOTAL_FORMS": "0",
            "comments-INITIAL_FORMS": "0",
            "test_childobjects-TOTAL_FORMS": "0",
            "test_childobjects-INITIAL_FORMS": "0",
            "test_synchronized_childobjects-TOTAL_FORMS": "0",
            "test_synchronized_childobjects-INITIAL_FORMS": "0",
        }
        response = self.client.post(
            reverse(
                "wagtailadmin_pages:add",
                args=["wagtail_localize_test", "testpage", self.en_homepage.id],
            ),
            post_data,
        )

        self.assertEqual(response.status_code, 302)

        new_page = TestPage.objects.child_of(self.en_homepage).get(slug="foo")

        # Check that it created aliases for the other locales
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
        self.assertFalse(
            TestPage.objects.filter(
                translation_key=new_page.translation_key, locale=self.es_locale
            ).exists()
        )

        # Creating the locale synchronisation should create the page in Spanish
        LocaleSynchronization.objects.create(
            locale=self.es_locale,
            sync_from=self.en_locale,
        )

        es_new_page = TestPage.objects.get(
            translation_key=new_page.translation_key, locale=self.es_locale
        )
        self.assertEqual(es_new_page.alias_of, new_page.page_ptr)

    def test_create_homepage_in_sync_source_locale(self):
        # Test's for a crash that happened when a homepage was created for a locale
        # that is the sync source of another
        # See https://github.com/wagtail/wagtail-localize/issues/245

        # Delete all homepages
        root = Page.objects.get(id=1)
        root.get_children().delete()
        root.refresh_from_db()

        # Create the spanish Locale Synchronisation
        LocaleSynchronization.objects.create(
            locale=self.es_locale,
            sync_from=self.en_locale,
        )

        # Create a homepage in English
        post_data = {
            "title": "Home",
            "slug": "home",
            "action-publish": "publish",
            "test_streamfield-count": "0",
            "test_synchronized_streamfield-count": "0",
            "comments-TOTAL_FORMS": "0",
            "comments-INITIAL_FORMS": "0",
            "test_childobjects-TOTAL_FORMS": "0",
            "test_childobjects-INITIAL_FORMS": "0",
            "test_synchronized_childobjects-TOTAL_FORMS": "0",
            "test_synchronized_childobjects-INITIAL_FORMS": "0",
        }
        response = self.client.post(
            reverse(
                "wagtailadmin_pages:add",
                args=["wagtail_localize_test", "testpage", root.id],
            ),
            post_data,
        )

        self.assertEqual(response.status_code, 302)

        # Create a homepage in English
        new_en_homepage = TestPage.objects.child_of(root).get(locale=self.en_locale)

        # Homepages in other languages should be created
        self.assertTrue(new_en_homepage.has_translation(self.fr_locale))
        self.assertTrue(new_en_homepage.has_translation(self.fr_ca_locale))
        self.assertTrue(new_en_homepage.has_translation(self.es_locale))

    def test_synchronize_tree_with_draft_status(self):
        """Test that pages are created with live=False when sync_page_status='DRAFT'"""
        from wagtail_localize.synctree import synchronize_tree

        # Create a live page in English
        live_page = self.en_homepage.add_child(
            instance=TestPage(title="Live Page", slug="live-page")
        )
        live_page.save_revision().publish()

        # Create a draft page in English
        draft_page = self.en_homepage.add_child(
            instance=TestPage(title="Draft Page", slug="draft-page")
        )
        draft_page.save_revision()
        # Ensure it's actually a draft by unpublishing it
        draft_page.unpublish()

        # Sync with DRAFT status
        synchronize_tree(self.en_locale, self.fr_locale, sync_page_status="DRAFT")

        # Check that both pages were created as drafts in French
        fr_live_page = TestPage.objects.get(
            translation_key=live_page.translation_key, locale=self.fr_locale
        )
        fr_draft_page = TestPage.objects.get(
            translation_key=draft_page.translation_key, locale=self.fr_locale
        )

        self.assertFalse(fr_live_page.live)
        self.assertFalse(fr_draft_page.live)

    def test_synchronize_tree_with_mirror_status(self):
        """Test that pages mirror source status when sync_page_status='MIRROR'"""
        from wagtail_localize.synctree import synchronize_tree

        # Create a live page in English
        live_page = self.en_homepage.add_child(
            instance=TestPage(title="Live Page", slug="live-page")
        )
        live_page.save_revision().publish()

        # Create a draft page in English
        draft_page = self.en_homepage.add_child(
            instance=TestPage(title="Draft Page", slug="draft-page")
        )
        draft_page.save_revision()
        # Ensure it's actually a draft by unpublishing it
        draft_page.unpublish()

        # Sync with MIRROR status (default)
        synchronize_tree(self.en_locale, self.fr_locale, sync_page_status="MIRROR")

        # Check that pages mirror the source status
        fr_live_page = TestPage.objects.get(
            translation_key=live_page.translation_key, locale=self.fr_locale
        )
        fr_draft_page = TestPage.objects.get(
            translation_key=draft_page.translation_key, locale=self.fr_locale
        )

        self.assertTrue(fr_live_page.live)
        self.assertFalse(fr_draft_page.live)

    def test_create_new_page_with_draft_sync(self):
        """Test that auto-sync of new pages respects draft setting"""
        # Update the existing sync to use DRAFT status
        locale_sync = LocaleSynchronization.objects.get(locale=self.fr_locale)
        locale_sync.sync_page_status = "DRAFT"
        locale_sync.save()

        # Create a new live page in English
        new_page = self.en_homepage.add_child(
            instance=TestPage(title="New Page", slug="new-page")
        )
        new_page.save_revision().publish()

        # Manually trigger the auto-sync since we're not using the admin interface
        from wagtail_localize.synctree import create_aliases_for_new_page

        create_aliases_for_new_page(new_page)

        # Check that the French version was created as draft
        try:
            fr_new_page = TestPage.objects.get(
                translation_key=new_page.translation_key, locale=self.fr_locale
            )
            self.assertFalse(fr_new_page.live)
        except TestPage.DoesNotExist:
            # If the page doesn't exist, check if there are any pages at all
            all_pages = TestPage.objects.filter(locale=self.fr_locale)
            self.fail(f"No French page found. Available pages: {list(all_pages)}")

    def test_create_new_page_with_mirror_sync(self):
        """Test that auto-sync of new pages respects mirror setting"""
        # Ensure sync is set to MIRROR (default)
        locale_sync = LocaleSynchronization.objects.get(locale=self.fr_locale)
        locale_sync.sync_page_status = "MIRROR"
        locale_sync.save()

        # Create a new live page in English
        new_page = self.en_homepage.add_child(
            instance=TestPage(title="New Page", slug="new-page")
        )
        new_page.save_revision().publish()

        # Manually trigger the auto-sync since we're not using the admin interface
        from wagtail_localize.synctree import create_aliases_for_new_page

        create_aliases_for_new_page(new_page)

        # Check that the French version mirrors the live status
        try:
            fr_new_page = TestPage.objects.get(
                translation_key=new_page.translation_key, locale=self.fr_locale
            )
            self.assertTrue(fr_new_page.live)
        except TestPage.DoesNotExist:
            # If the page doesn't exist, check if there are any pages at all
            all_pages = TestPage.objects.filter(locale=self.fr_locale)
            self.fail(f"No French page found. Available pages: {list(all_pages)}")

    def test_mixed_live_and_draft_pages(self):
        """Test that draft mode sets all pages to draft regardless of source status"""
        from wagtail_localize.synctree import synchronize_tree

        # Create multiple pages with different statuses
        live_page1 = self.en_homepage.add_child(
            instance=TestPage(title="Live Page 1", slug="live-page-1")
        )
        live_page1.save_revision().publish()

        live_page2 = self.en_homepage.add_child(
            instance=TestPage(title="Live Page 2", slug="live-page-2")
        )
        live_page2.save_revision().publish()

        draft_page = self.en_homepage.add_child(
            instance=TestPage(title="Draft Page", slug="draft-page")
        )
        draft_page.save_revision()

        # Sync with DRAFT status
        synchronize_tree(self.en_locale, self.fr_locale, sync_page_status="DRAFT")

        # Check that all pages are created as drafts
        for page in [live_page1, live_page2, draft_page]:
            fr_page = TestPage.objects.get(
                translation_key=page.translation_key, locale=self.fr_locale
            )
            self.assertFalse(fr_page.live)
