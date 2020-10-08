import json

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Locale

from wagtail_localize.models import (
    TranslationSource,
    String,
    StringTranslation,
    SourceDeletedError,
    MissingTranslationError,
    MissingRelatedObjectError,
    TranslationContext,
)
from wagtail_localize.segments import RelatedObjectSegmentValue
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import TestPage, TestSnippet, TestChildObject, TestSynchronizedChildObject, TestNonParentalChildObject


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


class TestGetOrCreateFromInstance(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")

    def test_create(self):
        source, created = TranslationSource.get_or_create_from_instance(self.snippet)

        self.assertTrue(created)
        self.assertEqual(source.object_id, self.snippet.translation_key)
        self.assertEqual(source.locale, self.snippet.locale)
        self.assertEqual(
            json.loads(source.content_json),
            {
                "pk": self.snippet.pk,
                "field": "This is some test content",
                "translation_key": str(self.snippet.translation_key),
                "locale": self.snippet.locale_id,
            },
        )
        self.assertTrue(source.created_at)

    def test_update(self):
        source = TranslationSource.objects.create(
            object_id=self.snippet.translation_key,
            specific_content_type=ContentType.objects.get_for_model(TestSnippet),
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "Some different content",  # Changed
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                }
            ),
            last_updated_at=timezone.now(),
        )

        new_source, created = TranslationSource.get_or_create_from_instance(self.snippet)

        self.assertEqual(source, new_source)
        self.assertEqual(
            json.loads(source.content_json)["field"], "Some different content"
        )
        self.assertEqual(
            json.loads(new_source.content_json)["field"], "Some different content"
        )


class TestUpdateOrCreateFromInstance(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")

    def test_create(self):
        source, created = TranslationSource.update_or_create_from_instance(self.snippet)

        self.assertTrue(created)
        self.assertEqual(source.object_id, self.snippet.translation_key)
        self.assertEqual(source.locale, self.snippet.locale)
        self.assertEqual(
            json.loads(source.content_json),
            {
                "pk": self.snippet.pk,
                "field": "This is some test content",
                "translation_key": str(self.snippet.translation_key),
                "locale": self.snippet.locale_id,
            },
        )
        self.assertTrue(source.created_at)

    def test_update(self):
        source = TranslationSource.objects.create(
            object_id=self.snippet.translation_key,
            specific_content_type=ContentType.objects.get_for_model(TestSnippet),
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "Some different content",  # Changed
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                }
            ),
            last_updated_at=timezone.now(),
        )

        new_source, created = TranslationSource.update_or_create_from_instance(self.snippet)

        self.assertFalse(created)

        self.assertEqual(source, new_source)
        self.assertEqual(
            json.loads(source.content_json)["field"], "Some different content"
        )
        self.assertEqual(
            json.loads(new_source.content_json)["field"], "This is some test content"
        )


class TestAsInstanceForPage(TestCase):
    def setUp(self):
        self.page = create_test_page(title="Test page", slug="test-page")
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)

    def test(self):
        # To show it actually is using the translation source and not the live object,
        # mess with the JSON content manually
        content = json.loads(self.source.content_json)

        content["title"] = "Changed title"
        self.source.content_json = json.dumps(content)
        self.source.save(update_fields=["content_json"])

        new_instance = self.source.as_instance()

        self.assertIsInstance(new_instance, TestPage)
        self.assertEqual(new_instance.id, self.page.id)
        self.assertEqual(new_instance.title, "Changed title")

    def test_raises_error_if_source_deleted(self):
        self.page.delete()

        with self.assertRaises(SourceDeletedError):
            self.source.as_instance()


class TestAsInstanceForSnippet(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")
        self.source, created = TranslationSource.get_or_create_from_instance(self.snippet)

    def test(self):
        # To show it actually is using the translation source and not the live object,
        # mess with the JSON content manually
        content = json.loads(self.source.content_json)

        content["field"] = "Some changed content"
        self.source.content_json = json.dumps(content)
        self.source.save(update_fields=["content_json"])

        new_instance = self.source.as_instance()

        self.assertIsInstance(new_instance, TestSnippet)
        self.assertEqual(new_instance.id, self.snippet.id)
        self.assertEqual(new_instance.field, "Some changed content")


class TestExportPO(TestCase):
    def setUp(self):
        self.page = create_test_page(title="Test page", slug="test-page", test_charfield="This is some test content")
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)

    def test_export_po(self):
        po = self.source.export_po()

        self.assertEqual(po.metadata.keys(), {'POT-Creation-Date', 'MIME-Version', 'Content-Type'})
        self.assertEqual(po.metadata['MIME-Version'], '1.0')
        self.assertEqual(po.metadata['Content-Type'], 'text/plain; charset=utf-8')

        self.assertEqual(len(po), 1)
        self.assertEqual(po[0].msgid, "This is some test content")
        self.assertEqual(po[0].msgctxt, "test_charfield")
        self.assertEqual(po[0].msgstr, "")
        self.assertFalse(po[0].obsolete)


class TestCreateOrUpdateTranslationForPage(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="Test snippet content")
        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
            test_snippet=self.snippet,
        )
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)
        self.source_locale = Locale.objects.get(language_code="en")
        self.dest_locale = Locale.objects.create(language_code="fr")

        # Translate the snippet
        self.translated_snippet = self.snippet.copy_for_translation(self.dest_locale)
        self.translated_snippet.field = "Tester le contenu de l'extrait"
        self.translated_snippet.save()

        # Add translation for test_charfield
        self.string = String.from_value(
            self.source_locale, StringValue.from_plaintext("This is some test content")
        )
        self.translation = StringTranslation.objects.create(
            translation_of=self.string,
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_charfield"
            ),
            data="Ceci est du contenu de test",
        )

    def test_create(self):
        new_page, created = self.source.create_or_update_translation(self.dest_locale)

        self.assertTrue(created)
        self.assertEqual(new_page.title, "Test page")
        self.assertEqual(new_page.slug, 'test-page-fr')
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertTrue(
            self.source.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_create_finds_available_slug(self):
        # Create a page with the `test-page-fr` slug already
        create_test_page(
            title="Test Page FR",
            slug="test-page-fr",
        )

        new_page, created = self.source.create_or_update_translation(self.dest_locale)

        self.assertTrue(created)
        self.assertEqual(new_page.slug, 'test-page-fr-1')

    def test_create_child(self):
        child_page = create_test_page(
            title="Child page",
            slug="child-page",
            parent=self.page,
            test_charfield="This is some test content",
            test_snippet=self.snippet,
        )
        child_source, created = TranslationSource.get_or_create_from_instance(child_page)

        translated_parent = self.page.copy_for_translation(self.dest_locale)

        # Create a translation for the new context
        StringTranslation.objects.create(
            translation_of=self.string,
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=child_page.translation_key, path="test_charfield"
            ),
            data="Ceci est du contenu de test",
        )

        new_page, created = child_source.create_or_update_translation(
            self.dest_locale
        )

        self.assertTrue(created)
        self.assertEqual(new_page.get_parent(), translated_parent)
        self.assertEqual(new_page.title, "Child page")
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.test_snippet, self.translated_snippet)
        self.assertEqual(new_page.translation_key, child_page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertTrue(
            child_source.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_update(self):
        self.page.copy_for_translation(self.dest_locale)

        new_page, created = self.source.create_or_update_translation(self.dest_locale)

        self.assertFalse(created)
        self.assertEqual(new_page.title, "Test page")
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.test_snippet, self.translated_snippet)
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertTrue(
            self.source.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_update_synchronised_fields(self):
        # Add a couple of initial child objects.
        # The first one will be deleted in the source page after initial translation. The sync should carry this deletion across.
        # The second won't be deleted so should remain in the translation
        self.page.test_synchronized_childobjects.add(
            TestSynchronizedChildObject(
                field="Test child object that existed before initial translation and was deleted"
            )
        )

        self.page.test_synchronized_childobjects.add(
            TestSynchronizedChildObject(
                field="Test child object that existed before initial translation and was not deleted"
            )
        )

        translated = self.page.copy_for_translation(self.dest_locale)

        self.page.test_synchronized_charfield = "Test synchronised content"
        self.page.test_synchronized_textfield = "Test synchronised content"
        self.page.test_synchronized_emailfield = "test@synchronised.content"
        self.page.test_synchronized_slugfield = "test-synchronised-content"
        self.page.test_synchronized_urlfield = "https://test.synchronised/content"
        self.page.test_synchronized_richtextfield = "<p>Test synchronised content</p>"
        # self.page.test_synchronized_streamfield = ""
        synchronized_snippet = TestSnippet.objects.create(field="Synchronised snippet")
        self.page.test_synchronized_snippet = synchronized_snippet
        self.page.test_synchronized_customfield = "Test synchronised content"

        # Add some child objects
        self.page.test_childobjects.add(
            TestChildObject(
                field="A test child object"
            )
        )

        # Remove one of the child objects to test that deletions are syncrhonised
        self.page.test_synchronized_childobjects.remove(self.page.test_synchronized_childobjects.get(field="Test child object that existed before initial translation and was deleted"))
        self.page.test_synchronized_childobjects.add(
            TestSynchronizedChildObject(
                field="A test synchronized object"
            )
        )

        # Non-parental child objects are created differently because modelcluster doesn't help us
        TestNonParentalChildObject.objects.create(
            page=self.page,
            field="A non-parental child object"
        )

        # Save the page
        revision = self.page.save_revision()
        revision.publish()
        self.page.refresh_from_db()
        source_with_changed_content, created = TranslationSource.update_or_create_from_instance(self.page)

        # Check translation hasn't been updated yet
        translated.refresh_from_db()
        self.assertEqual(translated.test_synchronized_charfield, "")

        # Update the original page again. This will make sure it's taking the content from the translation source and not the live version
        self.page.test_synchronized_charfield = (
            "Test synchronised content updated again"
        )
        self.page.save_revision().publish()

        (
            new_page,
            created,
        ) = source_with_changed_content.create_or_update_translation(
            self.dest_locale,
            fallback=True,
        )

        self.assertFalse(created)
        self.assertEqual(new_page, translated)
        self.assertEqual(
            new_page.test_synchronized_charfield, "Test synchronised content"
        )
        self.assertEqual(
            new_page.test_synchronized_charfield, "Test synchronised content"
        )
        self.assertEqual(
            new_page.test_synchronized_textfield, "Test synchronised content"
        )
        self.assertEqual(
            new_page.test_synchronized_emailfield, "test@synchronised.content"
        )
        self.assertEqual(
            new_page.test_synchronized_slugfield, "test-synchronised-content"
        )
        self.assertEqual(
            new_page.test_synchronized_urlfield, "https://test.synchronised/content"
        )
        self.assertEqual(
            new_page.test_synchronized_richtextfield, "<p>Test synchronised content</p>"
        )
        self.assertEqual(new_page.test_synchronized_snippet, synchronized_snippet)
        self.assertEqual(
            new_page.test_synchronized_customfield, "Test synchronised content"
        )

        # Translatable child objects should always be synchronised
        # Locale should be updated but translation key should be the same
        translatable_child_object = new_page.test_childobjects.get()
        self.assertEqual(translatable_child_object.field, "A test child object")
        self.assertEqual(translatable_child_object.locale, self.dest_locale)
        self.assertTrue(translatable_child_object.has_translation(self.source_locale))

        # Test both the non deleted and new synchronised child objects remain
        self.assertEqual(
            set(new_page.test_synchronized_childobjects.values_list('field', flat=True)),
            {"A test synchronized object", "Test child object that existed before initial translation and was not deleted"}
        )

        # Non parental child objects should be ignored
        self.assertFalse(new_page.test_nonparentalchildobjects.exists())

    def test_update_streamfields(self):
        # Streamfields are special in that they contain content that needs to be synchronised as well as
        # translatable content.

        # Copy page for translation, this will have a blank streamfield
        translated = self.page.copy_for_translation(self.dest_locale)

        # Set streamfield value on original
        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            [
                {
                    "id": "id",
                    "type": "test_charblock",
                    "value": "This is some test content",
                }
            ],
            is_lazy=True,
        )

        # Save the page
        revision = self.page.save_revision()
        revision.publish()
        self.page.refresh_from_db()
        source_with_streamfield, created = TranslationSource.update_or_create_from_instance(self.page)

        # Create a translation for the new context
        StringTranslation.objects.create(
            translation_of=self.string,
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_streamfield.id"
            ),
            data="Ceci est du contenu de test",
        )

        new_page, created = source_with_streamfield.create_or_update_translation(
            self.dest_locale
        )

        self.assertFalse(created)
        self.assertEqual(new_page, translated)

        # Check the block was copied into translation
        self.assertEqual(new_page.test_streamfield[0].id, "id")
        self.assertEqual(
            new_page.test_streamfield[0].value, "Ceci est du contenu de test"
        )

    def test_create_translations_not_ready(self):
        self.translation.delete()

        with self.assertRaises(MissingTranslationError) as e:
            self.source.create_or_update_translation(self.dest_locale)

        self.assertEqual(e.exception.segment.source, self.source)
        self.assertEqual(e.exception.segment.context.path, "test_charfield")
        self.assertEqual(e.exception.segment.string, self.string)
        self.assertEqual(e.exception.locale, self.dest_locale)

    def test_create_related_object_not_ready(self):
        self.translated_snippet.delete()

        with self.assertRaises(MissingRelatedObjectError) as e:
            self.source.create_or_update_translation(self.dest_locale)

        self.assertEqual(e.exception.segment.source, self.source)
        self.assertEqual(e.exception.segment.context.path, "test_snippet")
        self.assertEqual(e.exception.segment.object_id, self.snippet.translation_key)
        self.assertEqual(e.exception.locale, self.dest_locale)

    def test_create_not_ready_with_fallback_true(self):
        # Same as previous two tests, except we pass `fallback=True` this time
        # so it falls back to the source value instead of raising an exception.
        self.translation.delete()
        self.translated_snippet.delete()

        translated_page, created = self.source.create_or_update_translation(self.dest_locale, fallback=True)

        self.assertEqual(translated_page.test_snippet, self.snippet)
        self.assertEqual(translated_page.test_charfield, "This is some test content")

    def test_create_with_fallback_true(self):
        # Like the previous test, but this time we have valid data, so it shouldn't fallback
        translated_page, created = self.source.create_or_update_translation(self.dest_locale, fallback=True)

        self.assertEqual(translated_page.test_snippet, self.translated_snippet)
        self.assertEqual(translated_page.test_charfield, "Ceci est du contenu de test")


class TestGetEphemeralTranslatedInstance(TestCase):
    def setUp(self):
        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
            test_textfield="This is some more test content",
        )
        self.source, created = TranslationSource.get_or_create_from_instance(self.page)
        self.source_locale = Locale.objects.get(language_code="en")
        self.dest_locale = Locale.objects.create(language_code="fr")

        # Translate the page
        self.translated_page = self.page.copy_for_translation(self.dest_locale)

        # Add a test child object and update the test_textfield. Then update the translation source
        self.page.test_childobjects.add(TestChildObject(field="This is a test child object"))
        self.page.test_textfield = "Updated textfield"
        self.page.save_revision().publish()
        self.source.update_from_db()

        # Add translation for test_charfield
        self.translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data="This is some test content"),
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_charfield"
            ),
            data="Ceci est du contenu de test",
        )

        # Add translation for child object
        self.translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data="This is a test child object"),
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_childobjects.{}.field".format(self.page.test_childobjects.get().translation_key)
            ),
            data="Ceci est un objet enfant de test",
        )

    def test_get_ephemeral_translated_instance(self):
        new_page = self.source.get_ephemeral_translated_instance(self.dest_locale, fallback=True)

        self.assertEqual(new_page.id, self.translated_page.id)
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.test_textfield, "Updated textfield")
        self.assertEqual(new_page.test_childobjects.get().field, "Ceci est un objet enfant de test")
        self.assertFalse(
            self.source.translation_logs.filter(locale=self.dest_locale).exists()
        )

        # Check the saved page has not been changed
        self.translated_page.refresh_from_db()
        self.assertEqual(self.translated_page.title, "Test page")
        self.assertEqual(self.translated_page.test_charfield, "This is some test content")
        self.assertEqual(self.translated_page.test_textfield, "This is some more test content")
        self.assertFalse(self.translated_page.test_childobjects.exists())

    def test_without_fallback(self):
        # Should raise an error because we haven't translated test_textfield
        with self.assertRaises(MissingTranslationError):
            self.source.get_ephemeral_translated_instance(self.dest_locale)

        # Add a translation for test_textfield to make the error go away
        self.translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data="Updated textfield"),
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_textfield"
            ),
            data="Champ de texte mis à jour",
        )

        new_page = self.source.get_ephemeral_translated_instance(self.dest_locale)
        self.assertEqual(new_page.test_textfield, "Champ de texte mis à jour")
