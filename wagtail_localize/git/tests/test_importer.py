import logging
from unittest import mock

import polib
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from wagtail.core.models import Page, Locale
from wagtail_localize.models import TranslationSource, Translation, MissingRelatedObjectError
from wagtail_localize.test.models import TestPage

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
            test_textfield="The other test translatable field",
        )
        self.resource = Resource.get_for_object(self.source.object)
        self.locale = Locale.objects.create(language_code="fr")
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.locale,
        )

    def test_importer(self):
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

    def test_importer_warnings(self):
        po = create_test_po(
            [
                # Unknown string
                (
                    "test_charfield",
                    "Unknown string",
                    "Le champ traduisible de test",
                ),
                # Unknown context
                (
                    "unknown_context",
                    "The test translatable field",
                    "Le champ testable à traduire avec un contenu mis à jour",
                ),
                # String not used in context
                (
                    "test_charfield",
                    "The other test translatable field",
                    "Le champ traduisible de test",
                ),
            ]
        )

        logger = mock.MagicMock()
        importer = Importer("0" * 40, logger)
        importer.import_resource(self.translation, po)

        # Check that the warnings were logged
        logger.warning.assert_any_call("While translating 'Test page' into French: Unrecognised string 'Unknown string'")
        logger.warning.assert_any_call("While translating 'Test page' into French: Unrecognised context 'unknown_context'")
        logger.warning.assert_any_call("While translating 'Test page' into French: The string 'The other test translatable field' is not used in context  'test_charfield'")

    @mock.patch('wagtail_localize.models.Translation.save_target')
    def test_importer_missing_related_object(self, save_target):
        save_target.side_effect = MissingRelatedObjectError('segment', self.locale)

        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test translatable field",
                    "Le champ traduisible de test",
                )
            ]
        )

        logger = mock.MagicMock()
        importer = Importer("0" * 40, logger)
        importer.import_resource(self.translation, po)

        # Check a warning was logged
        logger.warning.assert_called_with("Unable to translate 'Test page' into French: Missing related object")

    @mock.patch('wagtail_localize.models.Translation.save_target')
    def test_importer_validation_error(self, save_target):
        save_target.side_effect = ValidationError({'slug': "This slug is already in use."})

        po = create_test_po(
            [
                (
                    "test_charfield",
                    "The test translatable field",
                    "Le champ traduisible de test",
                )
            ]
        )

        logger = mock.MagicMock()
        importer = Importer("0" * 40, logger)
        importer.import_resource(self.translation, po)

        # Check a warning was logged
        logger.warning.assert_called_with("Unable to translate 'Test page' into French: ValidationError({'slug': ['This slug is already in use.']})")


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
