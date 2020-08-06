import logging
import unittest

import polib
from django.test import TestCase
from django.utils import timezone

from wagtail.core.models import Page, Locale
from wagtail_localize.models import TranslationSource, Translation, MissingRelatedObjectError
from wagtail_localize.test.models import TestPage, TestSnippet

from wagtail_localize.git.importer import Importer
from wagtail_localize.git.models import Resource, SyncLog


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    source, created = TranslationSource.get_or_create_from_instance(page)
    return page, source


def create_test_po(entries):
    po = polib.POFile(wrapwidth=200)
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/html; charset=utf-8",
    }

    for entry in entries:
        po.append(polib.POEntry(msgctxt=entry[0], msgid=entry[1], msgstr=entry[2]))

    return po


class TestImporter(TestCase):
    def setUp(self):
        self.page, self.source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="The test translatable field",
            test_synchronized_charfield="The test synchronized field",
        )
        self.resource = Resource.get_for_object(self.source.object)
        self.locale = Locale.objects.create(language_code="fr")
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.locale,
        )

    def test_importer(self):
        # Create a new page
        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test translatable field",
                    "Le champ traduisible de test",
                )
            ]
        )

        importer = Importer("0" * 40, logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        # Check translated page was created
        translated_page = TestPage.objects.get(locale=self.locale)
        self.assertEqual(translated_page.translation_key, self.page.translation_key)
        self.assertEqual(
            translated_page.test_charfield, "Le champ traduisible de test"
        )
        self.assertEqual(
            translated_page.test_synchronized_charfield,
            "The test synchronized field",
        )

        # Check log
        log = SyncLog.objects.get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 40)
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, self.resource)
        self.assertEqual(log_resource.locale, self.locale)

        # Perform another import updating the page
        # Much easier to do it this way than trying to construct all the models manually to match the result of the last test
        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test translatable field",
                    "Le champ testable à traduire avec un contenu mis à jour",
                )
            ]
        )

        importer = Importer("0" * 39 + "1", logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        translated_page.refresh_from_db()
        self.assertEqual(translated_page.translation_key, self.page.translation_key)
        self.assertEqual(
            translated_page.test_charfield,
            "Le champ testable à traduire avec un contenu mis à jour",
        )
        self.assertEqual(
            translated_page.test_synchronized_charfield,
            "The test synchronized field",
        )

        # Check log
        log = SyncLog.objects.exclude(id=log.id).get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 39 + "1")
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, self.resource)
        self.assertEqual(log_resource.locale, self.locale)

    @unittest.expectedFailure  # FIXME
    def test_importer_creates_parent_if_parent_not_translated(self):
        child_page, child_source = create_test_page(
            title="Test child page",
            slug="test-child-page",
            test_charfield="The test child's translatable field",
            test_synchronized_charfield="The test synchronized field",
            parent=self.page,
        )
        child_resource = Resource.get_for_object(child_source.object)

        # Create translated child page
        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test child&#39;s translatable field",
                    "Le champ traduisible de test",
                )
            ]
        )

        importer = Importer("0" * 40, logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        # Check translated page and its parent were created
        self.assertTrue(
            child_page.get_translations().filter(locale=self.locale).exists()
        )
        self.assertTrue(
            self.page.get_translations().filter(locale=self.locale).exists()
        )
        self.assertFalse(self.page.get_translations().filter(locale=self.locale).live)

        # Check log
        log = SyncLog.objects.get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 40)
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, child_resource)
        self.assertEqual(log_resource.locale, self.locale)

        # Create parent page
        po = create_test_po(
            [("test_charfield", "The test translatable field", "",)]
        )

        importer = Importer("0" * 39 + "1", logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        # Check both translated pages were created
        translated_parent = self.page.get_translations().get(locale=self.locale)
        self.assertEqual(
            translated_parent.translation_key, self.page.translation_key
        )
        self.assertEqual(
            translated_parent.test_charfield, "Le champ traduisible de test"
        )
        self.assertEqual(
            translated_parent.test_synchronized_charfield,
            "The test synchronized field",
        )

        translated_child = child_page.get_translations().get(locale=self.locale)
        self.assertEqual(
            translated_child.translation_key, child_page.translation_key
        )
        self.assertEqual(
            translated_child.test_charfield, "Le champ traduisible de test"
        )
        self.assertEqual(
            translated_child.test_synchronized_charfield,
            "The test synchronized field",
        )

        # Check log
        log = SyncLog.objects.exclude(id=log.id).get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 39 + "1")
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, self.resource)
        self.assertEqual(log_resource.locale, self.locale)

    @unittest.expectedFailure  # FIXME
    def test_importer_doesnt_import_if_dependency_not_translated(self):
        self.page.test_snippet = TestSnippet.objects.create(field="Test content")
        self.page.save()

        # Create translation for snippet
        snippet_source, created = TranslationSource.get_or_create_from_instance(self.page.test_snippet)
        snippet_translation = Translation.objects.create(
            source=snippet_source,
            target_locale=self.locale,
        )
        snippet_resource = Resource.get_for_object(snippet_source.object)

        # Re submit translation for page so it is linked to the snippet
        page_source, created = TranslationSource.get_or_create_from_instance(self.page)
        self.translation.source = page_source
        self.translation.save()

        # Create page
        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test translatable field",
                    "Le champ traduisible de test",
                )
            ]
        )

        importer = Importer("0" * 40, logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        # Check translated page was not created
        self.assertFalse(
            self.page.get_translations().filter(locale=self.locale).exists()
        )

        # Manually updating the page should fail
        with self.assertRaises(MissingRelatedObjectError):
            self.translation.save_target()

        # Check log
        log = SyncLog.objects.get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 40)
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, self.resource)
        self.assertEqual(log_resource.locale, self.locale)

        # Translate snippet
        po = create_test_po(
            [("field", "Test content", "Tester le contenu",)]
        )

        importer = Importer("0" * 39 + "1", logging.getLogger("dummy"))
        importer.import_resource(snippet_translation, po)

        # Check translated snippet was created, but note that the page is not automatically created at this point
        translated_snippet = self.page.test_snippet.get_translation(self.locale)
        self.assertEqual(translated_snippet.field, "Tester le contenu")
        self.assertFalse(
            self.page.get_translations().filter(locale=self.locale).exists()
        )

        # Check log
        log = SyncLog.objects.exclude(id=log.id).get()
        self.assertEqual(log.action, SyncLog.ACTION_PULL)
        self.assertEqual(log.commit_id, "0" * 39 + "1")
        log_resource = log.resources.get()
        self.assertEqual(log_resource.resource, snippet_resource)
        self.assertEqual(log_resource.locale, self.locale)

        # Now if we manually update the page, it should translate it
        self.translation.save_target()

        # The translated page should've been created and linked with the snippet
        translated_page = self.page.get_translation(self.locale)
        self.assertEqual(translated_page.test_snippet, translated_snippet)


class TestImporterRichText(TestCase):
    def setUp(self):
        self.page, self.source = create_test_page(
            title="Test page",
            slug="test-page",
            test_richtextfield='<p><a href="https://www.example.com">The <b>test</b> translatable field</a>.</p>',
        )
        self.resource = Resource.get_for_object(self.source.object)
        self.locale = Locale.objects.create(language_code="fr")
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.locale,
        )

    def test_importer_rich_text(self):
        po = create_test_po(
            [
                (
                    "test_richtextfield",
                    '<a id="a1">The <b>test</b> translatable field</a>.',
                    '<a id="a1">Le champ traduisible de <b>test</b></a>.',
                )
            ]
        )

        importer = Importer("0" * 40, logging.getLogger("dummy"))
        importer.import_resource(self.translation, po)

        # Check translated page was created
        translated_page = TestPage.objects.get(locale=self.locale)
        self.assertEqual(translated_page.translation_key, self.page.translation_key)

        # Check rich text field was created correctly
        self.assertHTMLEqual(
            translated_page.test_richtextfield,
            '<p><a href="https://www.example.com">Le champ traduisible de <b>test</b></a>.</p>',
        )
