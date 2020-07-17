import json

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page

from wagtail_localize.models import Locale
from wagtail_localize.test.models import TestPage, TestSnippet
from wagtail_localize.translation.models import (
    TranslationSource,
    String,
    StringTranslation,
    SourceDeletedError,
    MissingTranslationError,
    MissingRelatedObjectError,
    TranslationContext,
    StringSegment,
    TemplateSegment,
    RelatedObjectSegment,
)
from wagtail_localize.translation.segments import TemplateSegmentValue, RelatedObjectSegmentValue
from wagtail_localize.translation.segments.extract import extract_segments
from wagtail_localize.translation.strings import StringValue


def insert_segments(revision, locale, segments):
    """
    Inserts the list of untranslated segments into translation memory
    """
    for segment in segments:
        if isinstance(segment, TemplateSegmentValue):
            TemplateSegment.from_value(revision, segment)
        elif isinstance(segment, RelatedObjectSegmentValue):
            RelatedObjectSegment.from_value(revision, segment)
        else:
            StringSegment.from_value(revision, locale, segment)


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    page_revision = page.save_revision()
    page_revision.publish()
    page.refresh_from_db()

    source, created = TranslationSource.from_instance(page)

    prepare_source(source)

    return page


def prepare_source(source):
    # Extract segments from source and save them into translation memory
    segments = extract_segments(source.as_instance())
    insert_segments(source, source.locale_id, segments)

    # Recurse into any related objects
    for segment in segments:
        if not isinstance(segment, RelatedObjectSegmentValue):
            continue

        related_source, created = TranslationSource.from_instance(
            segment.get_instance(source.locale)
        )
        prepare_source(related_source)


class TestFromInstance(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")

    def test_create(self):
        source, created = TranslationSource.from_instance(self.snippet)

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

    def test_creates_new_source_if_changed(self):
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
            created_at=timezone.now(),
        )

        new_source, created = TranslationSource.from_instance(self.snippet)

        self.assertTrue(created)
        self.assertNotEqual(source, new_source)
        self.assertEqual(
            json.loads(source.content_json)["field"], "Some different content"
        )
        self.assertEqual(
            json.loads(new_source.content_json)["field"], "This is some test content"
        )

    def test_reuses_existing_source_if_not_changed(self):
        source = TranslationSource.objects.create(
            object_id=self.snippet.translation_key,
            specific_content_type=ContentType.objects.get_for_model(TestSnippet),
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "This is some test content",
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                }
            ),
            created_at=timezone.now(),
        )

        new_source, created = TranslationSource.from_instance(self.snippet)

        self.assertFalse(created)
        self.assertEqual(source, new_source)

    def test_creates_new_source_if_forced(self):
        source = TranslationSource.objects.create(
            object_id=self.snippet.translation_key,
            specific_content_type=ContentType.objects.get_for_model(TestSnippet),
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "This is some test content",
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                }
            ),
            created_at=timezone.now(),
        )

        new_source, created = TranslationSource.from_instance(
            self.snippet, force=True
        )

        self.assertTrue(created)
        self.assertNotEqual(source, new_source)
        self.assertEqual(
            json.loads(source.content_json)["field"], "This is some test content"
        )
        self.assertEqual(
            json.loads(new_source.content_json)["field"], "This is some test content"
        )


class TestAsInstanceForPage(TestCase):
    def setUp(self):
        self.page = create_test_page(title="Test page", slug="test-page")
        self.source = TranslationSource.from_instance(self.page)[0]

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
        self.source = TranslationSource.from_instance(self.snippet)[0]

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


class TestCreateOrUpdateTranslationForPage(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="Test snippet content")
        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
            test_snippet=self.snippet,
        )
        self.source = TranslationSource.from_instance(self.page)[0]
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
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertTrue(
            self.source.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_create_child(self):
        child_page = create_test_page(
            title="Child page",
            slug="child-page",
            parent=self.page,
            test_charfield="This is some test content",
        )
        child_source = TranslationSource.from_instance(child_page)[0]

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
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertTrue(
            self.source.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_update_synchronised_fields(self):
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

        # Save the page
        revision = self.page.save_revision()
        revision.publish()
        self.page.refresh_from_db()
        source_with_translated_countent = TranslationSource.from_instance(self.page)[0]

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
        ) = source_with_translated_countent.create_or_update_translation(
            self.dest_locale
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
        source_with_streamfield = TranslationSource.from_instance(self.page)[0]
        source_with_streamfield.extract_segments()

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
