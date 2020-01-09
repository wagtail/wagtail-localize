import json

from django.test import TestCase
from django.utils import timezone
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page

from wagtail_localize.models import Language, Locale
from wagtail_localize.test.models import TestPage, TestSnippet
from wagtail_localize.translation.models import (
    TranslatableRevision,
    SegmentTranslation,
    Segment,
    MissingTranslationError,
    MissingRelatedObjectError,
    SegmentTranslationContext,
)
from wagtail_localize.translation.utils import insert_segments
from wagtail_localize.translation.segments import RelatedObjectValue
from wagtail_localize.translation.segments.extract import extract_segments


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    page_revision = page.save_revision()
    page_revision.publish()

    revision, created = TranslatableRevision.get_or_create_from_page_revision(
        page_revision
    )

    prepare_revision(revision)

    return page


def prepare_revision(revision):
    # Extract segments from revision and save them into translation memory
    segments = extract_segments(revision.as_instance())
    insert_segments(revision, revision.locale.language_id, segments)

    # Recurse into any related objects
    for segment in segments:
        if not isinstance(segment, RelatedObjectValue):
            continue

        related_revision, created = TranslatableRevision.from_instance(
            segment.get_instance(revision.locale)
        )
        prepare_revision(related_revision)


class TestGetOrCreateFromPageRevision(TestCase):
    def setUp(self):
        self.page = create_test_page(title="Test page", slug="test-page")

    def test_create(self):
        # Delete the revision that the Pontoon module creates on page publish
        TranslatableRevision.objects.all().delete()

        page_revision = self.page.get_latest_revision()

        # Refetch the page revision so that it has the generic Page object associated
        page_revision.refresh_from_db()

        revision, created = TranslatableRevision.get_or_create_from_page_revision(
            page_revision
        )

        self.assertTrue(created)

        self.assertEqual(revision.object_id, self.page.translation_key)
        self.assertEqual(revision.locale, self.page.locale)
        self.assertEqual(revision.page_revision, page_revision)
        self.assertEqual(revision.content_json, page_revision.content_json)
        self.assertEqual(revision.created_at, page_revision.created_at)

    def test_get(self):
        page_revision = self.page.get_latest_revision()
        revision, created = TranslatableRevision.get_or_create_from_page_revision(
            page_revision
        )

        self.assertFalse(created)


class TestFromInstance(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")

    def test_create(self):
        revision, created = TranslatableRevision.from_instance(self.snippet)

        self.assertTrue(created)

        self.assertEqual(revision.object_id, self.snippet.translation_key)
        self.assertEqual(revision.locale, self.snippet.locale)
        self.assertIsNone(revision.page_revision)
        self.assertEqual(
            json.loads(revision.content_json),
            {
                "pk": self.snippet.pk,
                "field": "This is some test content",
                "translation_key": str(self.snippet.translation_key),
                "locale": self.snippet.locale_id,
                "is_source_translation": True,
            },
        )
        self.assertTrue(revision.created_at)

    def test_creates_new_revision_if_changed(self):
        revision = TranslatableRevision.objects.create(
            object_id=self.snippet.translation_key,
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "Some different content",  # Changed
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                    "is_source_translation": True,
                }
            ),
            created_at=timezone.now(),
        )

        new_revision, created = TranslatableRevision.from_instance(self.snippet)

        self.assertTrue(created)
        self.assertNotEqual(revision, new_revision)
        self.assertEqual(
            json.loads(revision.content_json)["field"], "Some different content"
        )
        self.assertEqual(
            json.loads(new_revision.content_json)["field"], "This is some test content"
        )

    def test_reuses_existing_revision_if_not_changed(self):
        revision = TranslatableRevision.objects.create(
            object_id=self.snippet.translation_key,
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "This is some test content",
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                    "is_source_translation": True,
                }
            ),
            created_at=timezone.now(),
        )

        new_revision, created = TranslatableRevision.from_instance(self.snippet)

        self.assertFalse(created)
        self.assertEqual(revision, new_revision)

    def test_creates_new_revision_if_forced(self):
        revision = TranslatableRevision.objects.create(
            object_id=self.snippet.translation_key,
            locale=self.snippet.locale,
            content_json=json.dumps(
                {
                    "pk": self.snippet.pk,
                    "field": "This is some test content",
                    "translation_key": str(self.snippet.translation_key),
                    "locale": self.snippet.locale_id,
                    "is_source_translation": True,
                }
            ),
            created_at=timezone.now(),
        )

        new_revision, created = TranslatableRevision.from_instance(
            self.snippet, force=True
        )

        self.assertTrue(created)
        self.assertNotEqual(revision, new_revision)
        self.assertEqual(
            json.loads(revision.content_json)["field"], "This is some test content"
        )
        self.assertEqual(
            json.loads(new_revision.content_json)["field"], "This is some test content"
        )


class TestAsInstanceForPage(TestCase):
    def setUp(self):
        self.page = create_test_page(title="Test page", slug="test-page")
        self.revision = TranslatableRevision.get_or_create_from_page_revision(
            self.page.get_latest_revision()
        )[0]

    def test(self):
        # To show it actually is using the revision and not the live object,
        # mess with the JSON content manually
        content = json.loads(self.revision.content_json)

        content["title"] = "Changed title"
        self.revision.content_json = json.dumps(content)
        self.revision.save(update_fields=["content_json"])

        new_instance = self.revision.as_instance()

        self.assertIsInstance(new_instance, TestPage)
        self.assertEqual(new_instance.id, self.page.id)
        self.assertEqual(new_instance.title, "Changed title")


class TestAsInstanceForSnippet(TestCase):
    def setUp(self):
        self.snippet = TestSnippet.objects.create(field="This is some test content")
        self.revision = TranslatableRevision.from_instance(self.snippet)[0]

    def test(self):
        # To show it actually is using the revision and not the live object,
        # mess with the JSON content manually
        content = json.loads(self.revision.content_json)

        content["field"] = "Some changed content"
        self.revision.content_json = json.dumps(content)
        self.revision.save(update_fields=["content_json"])

        new_instance = self.revision.as_instance()

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
        self.revision = TranslatableRevision.get_or_create_from_page_revision(
            self.page.get_latest_revision()
        )[0]
        Language.objects.create(code="fr")
        self.source_locale = Locale.objects.get(language__code="en")
        self.dest_locale = Locale.objects.get(language__code="fr")

        # Translate the snippet
        self.translated_snippet = self.snippet.copy_for_translation(self.dest_locale)
        self.translated_snippet.field = "Tester le contenu de l'extrait"
        self.translated_snippet.save()

        # Add translation for test_charfield
        self.segment = Segment.from_text(
            self.source_locale.language, "This is some test content"
        )
        self.translation = SegmentTranslation.objects.create(
            translation_of=self.segment,
            language=self.dest_locale.language,
            context=SegmentTranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_charfield"
            ),
            text="Ceci est du contenu de test",
        )

    def test_create(self):
        new_page, created = self.revision.create_or_update_translation(self.dest_locale)

        self.assertTrue(created)
        self.assertEqual(new_page.title, "Test page")
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertFalse(new_page.is_source_translation)
        self.assertTrue(
            self.revision.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_create_child(self):
        child_page = create_test_page(
            title="Child page",
            slug="child-page",
            parent=self.page,
            test_charfield="This is some test content",
        )
        child_revision = TranslatableRevision.get_or_create_from_page_revision(
            child_page.get_latest_revision()
        )[0]

        translated_parent = self.page.copy_for_translation(self.dest_locale)

        # Create a translation for the new context
        SegmentTranslation.objects.create(
            translation_of=self.segment,
            language=self.dest_locale.language,
            context=SegmentTranslationContext.objects.get(
                object_id=child_page.translation_key, path="test_charfield"
            ),
            text="Ceci est du contenu de test",
        )

        new_page, created = child_revision.create_or_update_translation(
            self.dest_locale
        )

        self.assertTrue(created)
        self.assertEqual(new_page.get_parent(), translated_parent)
        self.assertEqual(new_page.title, "Child page")
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.translation_key, child_page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertFalse(new_page.is_source_translation)
        self.assertTrue(
            child_revision.translation_logs.filter(locale=self.dest_locale).exists()
        )

    def test_update(self):
        translated = self.page.copy_for_translation(self.dest_locale)

        new_page, created = self.revision.create_or_update_translation(self.dest_locale)

        self.assertFalse(created)
        self.assertEqual(new_page.title, "Test page")
        self.assertEqual(new_page.test_charfield, "Ceci est du contenu de test")
        self.assertEqual(new_page.translation_key, self.page.translation_key)
        self.assertEqual(new_page.locale, self.dest_locale)
        self.assertFalse(new_page.is_source_translation)
        self.assertTrue(
            self.revision.translation_logs.filter(locale=self.dest_locale).exists()
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
        revision_with_synchronised_content = TranslatableRevision.get_or_create_from_page_revision(
            revision
        )[
            0
        ]

        # Check translation hasn't been updated yet
        translated.refresh_from_db()
        self.assertEqual(translated.test_synchronized_charfield, "")

        # Update the original page again. This will make sure it's taking the content from the revision and not the live version
        self.page.test_synchronized_charfield = (
            "Test synchronised content updated again"
        )
        self.page.save_revision().publish()

        (
            new_page,
            created,
        ) = revision_with_synchronised_content.create_or_update_translation(
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
        revision_with_streamfield = TranslatableRevision.get_or_create_from_page_revision(
            revision
        )[
            0
        ]
        revision_with_streamfield.extract_segments()

        # Create a translation for the new context
        SegmentTranslation.objects.create(
            translation_of=self.segment,
            language=self.dest_locale.language,
            context=SegmentTranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_streamfield.id"
            ),
            text="Ceci est du contenu de test",
        )

        new_page, created = revision_with_streamfield.create_or_update_translation(
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
            self.revision.create_or_update_translation(self.dest_locale)

        self.assertEqual(e.exception.location.revision, self.revision)
        self.assertEqual(e.exception.location.context.path, "test_charfield")
        self.assertEqual(e.exception.location.segment, self.segment)
        self.assertEqual(e.exception.locale, self.dest_locale)

    def test_create_related_object_not_ready(self):
        self.translated_snippet.delete()

        with self.assertRaises(MissingRelatedObjectError) as e:
            self.revision.create_or_update_translation(self.dest_locale)

        self.assertEqual(e.exception.location.revision, self.revision)
        self.assertEqual(e.exception.location.context.path, "test_snippet")
        self.assertEqual(e.exception.location.object_id, self.snippet.translation_key)
        self.assertEqual(e.exception.locale, self.dest_locale)
