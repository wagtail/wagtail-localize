from django.test import TestCase

from wagtail.core.models import Page

from wagtail_localize.compat import sync_fields_with, sync_child_relations_with
from wagtail_localize.test.models import (
    TestPage,
    TestHomePage,
    TestSynchronizedChildObject,
)


class TestSyncFieldsWith(TestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=1)

        self.about_page = self.root_page.add_child(
            instance=TestPage(title="About us", slug="about", test_charfield="hello")
        )

        # Create the other page under an index so it doesn't break when it syncs the slug
        self.an_index = self.root_page.add_child(
            instance=TestPage(
                title="An index", slug="an-index", test_charfield="An index"
            )
        )

        self.another_page = self.an_index.add_child(
            instance=TestPage(
                title="Another page", slug="another-page", test_charfield="hello world"
            )
        )

    def test(self):
        sync_fields_with(
            self.another_page, self.about_page, exclude_fields=["translation_key"]
        )
        self.another_page.save()
        self.another_page.refresh_from_db()

        # Check the fields that should be copied
        self.assertEqual(self.another_page.title, "About us")
        self.assertEqual(self.another_page.draft_title, "About us")
        self.assertEqual(self.another_page.slug, "about")
        self.assertEqual(self.another_page.url_path, "/an-index/about/")
        self.assertEqual(self.another_page.test_charfield, "hello")

        # Check the page position hasn't changed
        self.assertEqual(self.another_page.get_parent(), self.an_index)

    def test_exclude(self):
        sync_fields_with(
            self.another_page,
            self.about_page,
            exclude_fields=["title", "slug", "translation_key"],
        )
        self.another_page.save()
        self.another_page.refresh_from_db()

        # Check the fields that should be copied
        self.assertEqual(self.another_page.title, "Another page")
        self.assertEqual(self.another_page.draft_title, "Another page")
        self.assertEqual(self.another_page.slug, "another-page")
        self.assertEqual(self.another_page.url_path, "/an-index/another-page/")
        self.assertEqual(self.another_page.test_charfield, "hello")

        # Check the page position hasn't changed
        self.assertEqual(self.another_page.get_parent(), self.an_index)

    def test_pages_must_be_same_type(self):
        different_type_page = self.root_page.add_child(
            instance=TestHomePage(title="Event", slug="event",)
        )

        with self.assertRaises(TypeError) as e:
            sync_fields_with(self.another_page, different_type_page)

        self.assertEqual(str(e.exception), "Page types do not match.")


class TestSyncChildRelationsWith(TestCase):
    def setUp(self):
        self.root_page = Page.objects.get(id=1)

        self.about_page = self.root_page.add_child(
            instance=TestPage(title="About us", slug="about", test_charfield="hello")
        )

        TestSynchronizedChildObject.objects.create(page=self.about_page, field="test")

        self.another_page = self.root_page.add_child(
            instance=TestPage(
                title="Another page", slug="another-page", test_charfield="hello world"
            )
        )

    def test(self):
        sync_child_relations_with(self.another_page, self.about_page)
        self.another_page.refresh_from_db()

        # Check that the test_synchronized_childobjects were copied
        self.assertEqual(
            self.another_page.test_synchronized_childobjects.count(),
            1,
            "Child objects weren't copied",
        )
        first_copied_speaker_id = (
            self.another_page.test_synchronized_childobjects.get().id
        )

        # Check that the test_synchronized_childobjects weren't removed from old page
        self.assertEqual(
            self.about_page.test_synchronized_childobjects.count(),
            1,
            "Child objects were removed from the original page",
        )

        # Now sync again
        sync_child_relations_with(self.another_page, self.about_page)
        self.another_page.refresh_from_db()

        # Check that they weren't copied again
        self.assertEqual(
            self.another_page.test_synchronized_childobjects.count(),
            1,
            "Child objects were copied twice",
        )

        # The ID shouldn't change
        self.assertTrue(
            self.another_page.test_synchronized_childobjects.filter(
                id=first_copied_speaker_id
            ).exists()
        )

        # Add another speaker and sync again
        new_speaker = self.about_page.test_synchronized_childobjects.create(
            field="new test"
        )
        sync_child_relations_with(self.another_page, self.about_page)
        self.another_page.refresh_from_db()

        # Check that the test_synchronized_childobjects were copied
        self.assertEqual(
            self.another_page.test_synchronized_childobjects.count(),
            2,
            "New child objects weren't copied",
        )

        # Check that the test_synchronized_childobjects weren't removed from old page
        self.assertEqual(
            self.about_page.test_synchronized_childobjects.count(),
            2,
            "New child objects were removed from the original page",
        )

        # Delete the new speaker and sync again
        new_speaker.delete()

        # Need to do a hard refresh in order to get modelcluster to refresh
        about_page = TestPage.objects.get(id=self.about_page.id)

        sync_child_relations_with(self.another_page, about_page)
        self.another_page.refresh_from_db()

        # Check that the test_synchronized_childobjects were copied
        self.assertEqual(
            self.another_page.test_synchronized_childobjects.count(),
            1,
            "New child objects weren't deleted",
        )

        # Check that the test_synchronized_childobjects weren't removed from old page
        self.assertEqual(
            about_page.test_synchronized_childobjects.count(),
            1,
            "new child objects weren't removed from the original page",
        )
