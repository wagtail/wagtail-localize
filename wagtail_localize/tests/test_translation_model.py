from django.test import TestCase
from wagtail.core.models import Page, Locale

from wagtail_localize.models import (
    TranslationSource,
    String,
    StringTranslation,
    TranslationContext,
    StringSegment,
    TemplateSegment,
    RelatedObjectSegment,
    Translation,
    CannotSaveDraftError,
)
from wagtail_localize.segments import TemplateSegmentValue, RelatedObjectSegmentValue
from wagtail_localize.segments.extract import extract_segments
from wagtail_localize.test.models import TestPage, TestSnippet


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


class TestGetProgress(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content"
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            object=self.source.object,
            target_locale=self.fr_locale,
            source=self.source,
        )

        self.test_charfield_context = TranslationContext.objects.get(path="test_charfield")
        self.test_textfield_context = TranslationContext.objects.get(path="test_textfield")

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


class TestGetStatus(TestCase):
    def setUp(self):
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-slug",
            test_charfield="Test content",
            test_textfield="More test content"
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            object=self.source.object,
            target_locale=self.fr_locale,
            source=self.source,
        )

        self.test_charfield_context = TranslationContext.objects.get(path="test_charfield")
        self.test_textfield_context = TranslationContext.objects.get(path="test_textfield")

        self.test_content_string = String.objects.get(data="Test content")
        self.more_test_content_string = String.objects.get(data="More test content")

    def test_get_status_display(self):
        self.assertEqual(self.translation.get_status_display(), "Waiting for translations")

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
            test_textfield="More test content"
        )
        self.source = TranslationSource.objects.get()
        self.translation = Translation.objects.create(
            object=self.source.object,
            target_locale=self.fr_locale,
            source=self.source,
        )

        self.test_charfield_context = TranslationContext.objects.get(path="test_charfield")
        self.test_textfield_context = TranslationContext.objects.get(path="test_textfield")

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
        source, created = TranslationSource.from_instance(snippet)
        source.extract_segments()
        translation = Translation.objects.create(
            object=source.object,
            target_locale=self.fr_locale,
            source=source,
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
        source, created = TranslationSource.from_instance(snippet)
        source.extract_segments()
        translation = Translation.objects.create(
            object=source.object,
            target_locale=self.fr_locale,
            source=source,
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
