from unittest import mock

import polib

from django.test import TestCase
from django.utils import timezone
from wagtail.core.models import Locale, Page

from wagtail_localize.models import (
    CannotSaveDraftError,
    NoViewRestrictionsError,
    String,
    StringNotUsedInContext,
    StringTranslation,
    Translation,
    TranslationContext,
    TranslationSource,
    UnknownContext,
    UnknownString,
)
from wagtail_localize.segments import RelatedObjectSegmentValue
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import TestPage, TestSnippet


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    page_revision = page.save_revision()
    page_revision.publish()
    page.refresh_from_db()

    source, created = TranslationSource.get_or_create_from_instance(page)

    prepare_source(source)

    return page


def prepare_source(source):
    # Recurse into any related objects
    for segment in source.relatedobjectsegment_set.all():
        if not isinstance(segment, RelatedObjectSegmentValue):
            continue

        related_source, created = TranslationSource.get_or_create_from_instance(
            segment.get_instance(source.locale)
        )
        prepare_source(related_source)


class TestGetProgress(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

        self.test_charfield_context = TranslationContext.objects.get(
            path="test_charfield"
        )
        self.test_textfield_context = TranslationContext.objects.get(
            path="test_textfield"
        )

        self.test_content_string = String.objects.get(data="Test content")
        self.more_test_content_string = String.objects.get(data="More test content")

    def test_get_progress(self):
        progress = self.translation.get_progress()
        self.assertEqual(progress, (2, 0))

    def test_get_progress_with_translations(self):
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_textfield_context,
            locale=self.fr_locale,
            data="Plus de contenu de test",
        )

        progress = self.translation.get_progress()
        self.assertEqual(progress, (2, 2))

    def test_get_progress_with_translations_in_different_locale(self):
        # Same as before but with a different locale. These shouldn't count
        de_locale = Locale.objects.create(language_code="de")

        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=de_locale,
            data="Testinhalt",
        )

        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_textfield_context,
            locale=de_locale,
            data="Mehr Testinhalte",
        )

        progress = self.translation.get_progress()
        self.assertEqual(progress, (2, 0))

    def test_get_progress_with_translations_in_different_context(self):
        # Same as before but swap the contexts of the translations. The translations shouldn't count
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_textfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Plus de contenu de test",
        )

        progress = self.translation.get_progress()
        self.assertEqual(progress, (2, 0))


class TestExportPO(TestCase):
    def setUp(self):
        self.en_locale = Locale.objects.get(language_code="en")
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
            test_textfield="This is some test content",
        )
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)

        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

    def test_export_po(self):
        po = self.translation.export_po()

        self.assertEqual(
            po.metadata.keys(),
            {
                "POT-Creation-Date",
                "MIME-Version",
                "Content-Type",
                "X-WagtailLocalize-TranslationID",
            },
        )
        self.assertEqual(po.metadata["MIME-Version"], "1.0")
        self.assertEqual(po.metadata["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(
            po.metadata["X-WagtailLocalize-TranslationID"], str(self.translation.uuid)
        )

        self.assertEqual(len(po), 2)
        self.assertEqual(po[0].msgid, "This is some test content")
        self.assertEqual(po[0].msgctxt, "test_charfield")
        self.assertEqual(po[0].msgstr, "")
        self.assertFalse(po[0].obsolete)

        # Test with the exact same content twice
        # This checks for https://github.com/wagtail/wagtail-localize/issues/253
        self.assertEqual(po[1].msgid, "This is some test content")
        self.assertEqual(po[1].msgctxt, "test_textfield")
        self.assertEqual(po[1].msgstr, "")
        self.assertFalse(po[1].obsolete)

    def test_export_po_with_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="This is some test content"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Contenu de test",
        )

        po = self.translation.export_po()

        self.assertEqual(
            po.metadata.keys(),
            {
                "POT-Creation-Date",
                "MIME-Version",
                "Content-Type",
                "X-WagtailLocalize-TranslationID",
            },
        )
        self.assertEqual(po.metadata["MIME-Version"], "1.0")
        self.assertEqual(po.metadata["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(
            po.metadata["X-WagtailLocalize-TranslationID"], str(self.translation.uuid)
        )

        self.assertEqual(len(po), 2)
        self.assertEqual(po[0].msgid, "This is some test content")
        self.assertEqual(po[0].msgctxt, "test_charfield")
        self.assertEqual(po[0].msgstr, "Contenu de test")
        self.assertFalse(po[0].obsolete)

        # Test with the exact same content twice
        # But note that this context doesn't have a translation!
        # This checks for https://github.com/wagtail/wagtail-localize/issues/253
        self.assertEqual(po[1].msgid, "This is some test content")
        self.assertEqual(po[1].msgctxt, "test_textfield")
        self.assertEqual(po[1].msgstr, "")
        self.assertFalse(po[1].obsolete)

    def test_export_po_with_obsolete_translation(self):
        obsolete_string = String.from_value(
            self.en_locale, StringValue("This is an obsolete string")
        )
        String.from_value(
            self.en_locale,
            StringValue("This is an obsolete string that was never translated"),
        )

        StringTranslation.objects.create(
            translation_of=obsolete_string,
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Ceci est une chaîne obsolète",
        )

        po = self.translation.export_po()

        self.assertEqual(
            po.metadata.keys(),
            {
                "POT-Creation-Date",
                "MIME-Version",
                "Content-Type",
                "X-WagtailLocalize-TranslationID",
            },
        )
        self.assertEqual(po.metadata["MIME-Version"], "1.0")
        self.assertEqual(po.metadata["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(
            po.metadata["X-WagtailLocalize-TranslationID"], str(self.translation.uuid)
        )

        # The non-obsolete strings come first
        self.assertEqual(len(po), 3)
        self.assertEqual(po[0].msgid, "This is some test content")
        self.assertEqual(po[0].msgctxt, "test_charfield")
        self.assertEqual(po[0].msgstr, "")
        self.assertFalse(po[0].obsolete)

        self.assertEqual(po[1].msgid, "This is some test content")
        self.assertEqual(po[1].msgctxt, "test_textfield")
        self.assertEqual(po[1].msgstr, "")
        self.assertFalse(po[1].obsolete)

        # Then the obsolete string
        self.assertEqual(po[2].msgid, "This is an obsolete string")
        self.assertEqual(po[2].msgctxt, "test_charfield")
        self.assertEqual(po[2].msgstr, "Ceci est une chaîne obsolète")
        self.assertTrue(po[2].obsolete)

        # Obsolete strings that never had a translation don't get exported


class TestImportPO(TestCase):
    def setUp(self):
        self.en_locale = Locale.objects.get(language_code="en")
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
        )
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)

        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

    def test_import_po(self):
        obsolete_string = String.from_value(
            self.en_locale, StringValue("This is an obsolete string")
        )
        StringTranslation.objects.create(
            translation_of=obsolete_string,
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Ceci est une chaîne obsolète",
        )

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="This is some test content",
                msgctxt="test_charfield",
                msgstr="Contenu de test",
            )
        )

        po.append(
            polib.POEntry(
                msgid="This is an obsolete string",
                msgctxt="test_charfield",
                msgstr="C'est encore une chaîne obsolète",
                obsolete=True,
            )
        )

        warnings = self.translation.import_po(po)
        self.assertEqual(warnings, [])

        translation = StringTranslation.objects.get(
            translation_of__data="This is some test content"
        )
        self.assertEqual(
            translation.context, TranslationContext.objects.get(path="test_charfield")
        )
        self.assertEqual(translation.locale, self.fr_locale)
        self.assertEqual(translation.data, "Contenu de test")

        # Obsolete strings still get updated
        translation = StringTranslation.objects.get(
            translation_of__data="This is an obsolete string"
        )
        self.assertEqual(
            translation.context, TranslationContext.objects.get(path="test_charfield")
        )
        self.assertEqual(translation.locale, self.fr_locale)
        self.assertEqual(
            translation.data,
            "C'est encore une chaîne obsolète",
        )

    def test_import_po_deletes_translations(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="This is some test content"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Contenu de test",
        )

        StringTranslation.objects.create(
            translation_of=String.from_value(
                self.en_locale, StringValue("This is an obsolete string")
            ),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Ceci est une chaîne obsolète",
        )

        # Create an empty PO file
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.translation.uuid),
        }

        warnings = self.translation.import_po(po, delete=True)
        self.assertEqual(warnings, [])

        # Should delete both the translations
        self.assertFalse(StringTranslation.objects.exists())

    def test_import_po_with_invalid_translation_id(self):
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": "foo",
        }

        po.append(
            polib.POEntry(
                msgid="This is some test content",
                msgctxt="test_charfield",
                msgstr="Contenu de test",
            )
        )

        warnings = self.translation.import_po(po)
        self.assertEqual(warnings, [])

        # Should delete both the translations
        self.assertFalse(StringTranslation.objects.exists())

    def test_import_po_with_valid_string_clears_has_error_flag(self):
        translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data="This is some test content"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data=(
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation."
            ),
            has_error=True,
            field_error="Ensure this value has at most 255 characters (it has 329).",
        )
        self.assertTrue(translation.has_error)

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="This is some test content",
                msgctxt="test_charfield",
                msgstr="Contenu de test",
            )
        )

        warnings = self.translation.import_po(po)
        self.assertEqual(warnings, [])

        translation.refresh_from_db()
        self.assertEqual(
            translation.context, TranslationContext.objects.get(path="test_charfield")
        )
        self.assertEqual(translation.locale, self.fr_locale)
        self.assertEqual(translation.data, "Contenu de test")
        self.assertFalse(translation.has_error)

    def test_warnings(self):
        String.from_value(
            self.en_locale,
            StringValue(
                "This string exists in the database but isn't relevant to this object"
            ),
        )

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="This string exists in the database but isn't relevant to this object",
                msgctxt="test_charfield",
                msgstr="Contenu de test",
            )
        )

        po.append(
            polib.POEntry(
                msgid="This string doesn't exist",
                msgctxt="test_charfield",
                msgstr="Contenu de test",
            )
        )

        po.append(
            polib.POEntry(
                msgid="This is some test content",
                msgctxt="invalidcontext",
                msgstr="Contenu de test",
            )
        )

        warnings = self.translation.import_po(po)

        self.assertEqual(
            warnings,
            [
                StringNotUsedInContext(
                    0,
                    "This string exists in the database but isn't relevant to this object",
                    "test_charfield",
                ),
                UnknownString(1, "This string doesn't exist"),
                UnknownContext(2, "invalidcontext"),
            ],
        )


class TestGetStatus(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

        self.test_charfield_context = TranslationContext.objects.get(
            path="test_charfield"
        )
        self.test_textfield_context = TranslationContext.objects.get(
            path="test_textfield"
        )

        self.test_content_string = String.objects.get(data="Test content")
        self.more_test_content_string = String.objects.get(data="More test content")

    def test_get_status_display(self):
        self.assertEqual(
            self.translation.get_status_display(), "Waiting for translations"
        )

    def test_get_status_display_with_translations(self):
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_textfield_context,
            locale=self.fr_locale,
            data="Plus de contenu de test",
        )

        self.assertEqual(self.translation.get_status_display(), "Up to date")


class TestSaveTarget(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

        self.test_charfield_context = TranslationContext.objects.get(
            path="test_charfield"
        )
        self.test_textfield_context = TranslationContext.objects.get(
            path="test_textfield"
        )

        self.test_content_string = String.objects.get(data="Test content")
        self.more_test_content_string = String.objects.get(data="More test content")

    def test_save_target(self):
        self.translation.save_target()

        # Should create the page with English content
        translated_page = self.page.get_translation(self.fr_locale)
        self.assertEqual(translated_page.test_charfield, "Test content")
        self.assertEqual(translated_page.test_textfield, "More test content")

        self.assertTrue(translated_page.live)

    def test_save_target_as_draft(self):
        self.translation.save_target(publish=False)

        # Should create the page with English content
        translated_page = self.page.get_translation(self.fr_locale)
        self.assertEqual(translated_page.test_charfield, "Test content")
        self.assertEqual(translated_page.test_textfield, "More test content")

        self.assertFalse(translated_page.live)

    def test_save_target_with_translations(self):
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_textfield_context,
            locale=self.fr_locale,
            data="Plus de contenu de test",
        )

        self.translation.save_target()

        translated_page = self.page.get_translation(self.fr_locale)
        self.assertEqual(translated_page.test_charfield, "Contenu de test")
        self.assertEqual(translated_page.test_textfield, "Plus de contenu de test")

    def test_save_target_with_partial_translations(self):
        StringTranslation.objects.create(
            translation_of=self.more_test_content_string,
            context=self.test_textfield_context,
            locale=self.fr_locale,
            data="Plus de contenu de test",
        )

        self.translation.save_target()

        translated_page = self.page.get_translation(self.fr_locale)
        self.assertEqual(translated_page.test_charfield, "Test content")
        self.assertEqual(translated_page.test_textfield, "Plus de contenu de test")

    def test_save_target_snippet(self):
        snippet = TestSnippet.objects.create(field="Test content")
        source, created = TranslationSource.get_or_create_from_instance(snippet)
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )

        field_context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=field_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        translation.save_target()

        translated_snippet = snippet.get_translation(self.fr_locale)
        self.assertEqual(translated_snippet.field, "Contenu de test")

    def test_save_target_cant_save_snippet_as_draft(self):
        snippet = TestSnippet.objects.create(field="Test content")
        source, created = TranslationSource.get_or_create_from_instance(snippet)
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )

        field_context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=field_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )

        with self.assertRaises(CannotSaveDraftError):
            translation.save_target(publish=False)


class TestDeleteSourceDisablesTranslation(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

    def test_page(self):
        page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )

        source = TranslationSource.objects.get()
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )

        translation.refresh_from_db()
        self.assertTrue(translation.enabled)

        page.delete()

        translation.refresh_from_db()
        self.assertFalse(translation.enabled)

    def test_snippet(self):
        snippet = TestSnippet.objects.create(field="Test content")

        source, created = TranslationSource.get_or_create_from_instance(snippet)
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )

        translation.refresh_from_db()
        self.assertTrue(translation.enabled)

        snippet.delete()

        translation.refresh_from_db()
        self.assertFalse(translation.enabled)


class TestDeleteDestinationDisablesTranslation(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.es_locale = Locale.objects.create(language_code="es")

    def test_page(self):
        page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )

        source = TranslationSource.objects.get()
        fr_translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )
        fr_translation.save_target()

        # Create a separate spanish translation to make sure that isn't disabled
        es_translation = Translation.objects.create(
            source=source,
            target_locale=self.es_locale,
        )
        es_translation.save_target()

        fr_translation.refresh_from_db()
        es_translation.refresh_from_db()
        self.assertTrue(fr_translation.enabled)
        self.assertTrue(es_translation.enabled)

        page.get_translation(self.fr_locale).delete()

        fr_translation.refresh_from_db()
        es_translation.refresh_from_db()
        self.assertFalse(fr_translation.enabled)
        self.assertTrue(es_translation.enabled)

    def test_snippet(self):
        snippet = TestSnippet.objects.create(field="Test content")

        source, created = TranslationSource.get_or_create_from_instance(snippet)
        fr_translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )
        fr_translation.save_target()

        # Create a separate spanish translation to make sure that isn't disabled
        es_translation = Translation.objects.create(
            source=source,
            target_locale=self.es_locale,
        )
        es_translation.save_target()

        fr_translation.refresh_from_db()
        es_translation.refresh_from_db()
        self.assertTrue(fr_translation.enabled)
        self.assertTrue(es_translation.enabled)

        snippet.get_translation(self.fr_locale).delete()

        fr_translation.refresh_from_db()
        es_translation.refresh_from_db()
        self.assertFalse(fr_translation.enabled)
        self.assertTrue(es_translation.enabled)


class TestTranslationSourceViewRestrictions(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content",
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.fr_locale,
        )

    @mock.patch("wagtail_localize.models.TranslationSource.sync_view_restrictions")
    @mock.patch.object(
        TranslationSource, "get_translated_instance", side_effect=Page.DoesNotExist()
    )
    def test_update_target_view_restrictions_with_missing_translation(
        self, get_translated_instance, sync_view_restrictions
    ):
        self.source.update_target_view_restrictions(self.fr_locale)

        self.assertEqual(get_translated_instance.call_count, 1)
        self.assertEqual(sync_view_restrictions.call_count, 0)

    @mock.patch("wagtail_localize.models.TranslationSource.get_translated_instance")
    def test_update_target_restrictions_ignores_snippets(self, get_translated_instance):
        snippet = TestSnippet.objects.create(field="Test content")
        source, created = TranslationSource.get_or_create_from_instance(snippet)

        source.update_target_view_restrictions(self.fr_locale)
        self.assertEqual(get_translated_instance.call_count, 0)

    def test_sync_view_restrictions_raises_exception_for_snippets(self):
        snippet = TestSnippet.objects.create(field="Test content")
        source, created = TranslationSource.get_or_create_from_instance(snippet)

        with self.assertRaises(NoViewRestrictionsError):
            source.sync_view_restrictions(snippet, snippet)
