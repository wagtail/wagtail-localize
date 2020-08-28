import uuid
import unittest

from django.test import TestCase

from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Locale

from wagtail_localize.fields import copy_synchronised_fields
from wagtail_localize.segments import (
    StringSegmentValue,
    TemplateSegmentValue,
    RelatedObjectSegmentValue,
)
from wagtail_localize.segments.ingest import ingest_segments
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import TestPage, TestSnippet, TestChildObject


def make_test_page(**kwargs):
    root_page = Page.objects.get(id=1)
    kwargs.setdefault("title", "Test page")
    return root_page.add_child(instance=TestPage(**kwargs))


RICH_TEXT_TEST_INPUT = '<h1>This is a heading</h1><p>This is a paragraph. &lt;foo&gt; <b>Bold text</b></p><ul><li><a href="http://example.com">This is a link</a></li></ul>'

RICH_TEXT_TEST_FRENCH_SEGMENTS = [
    TemplateSegmentValue(
        "",
        "html",
        '<h1><text position="0"></text></h1><p><text position="1"></text></p><ul><li><text position="2"></text></li></ul>',
        3,
        order=9,
    ),
    StringSegmentValue("", "Ceci est une rubrique", order=10),
    StringSegmentValue.from_source_html(
        "",
        'Ceci est un paragraphe. &lt;foo&gt; <b>Texte en gras</b>',
        order=11,
    ),
    StringSegmentValue(
        "",
        StringValue('<a id="a1">Ceci est un lien</a>'),
        attrs={
            "a1": {"href": "http://example.com"}
        },
        order=12,
    ),
]

RICH_TEXT_TEST_OUTPUT = '<h1>Ceci est une rubrique</h1><p>Ceci est un paragraphe. &lt;foo&gt; <b>Texte en gras</b></p><ul><li><a href="http://example.com">Ceci est un lien</a></li></ul>'


class TestSegmentIngestion(TestCase):
    def setUp(self):
        self.src_locale = Locale.get_default()
        self.locale = Locale.objects.create(language_code="fr")

    def test_charfield(self):
        page = make_test_page(test_charfield="Test content")
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_charfield", "Tester le contenu")],
        )

        self.assertEqual(translated_page.test_charfield, "Tester le contenu")

    def test_textfield(self):
        page = make_test_page(test_textfield="Test content")
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_textfield", "Tester le contenu")],
        )

        self.assertEqual(translated_page.test_textfield, "Tester le contenu")

    def test_emailfield(self):
        page = make_test_page(test_emailfield="test@example.com")
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_emailfield", "test@example.fr")],
        )

        self.assertEqual(translated_page.test_emailfield, "test@example.fr")

    def test_slugfield(self):
        page = make_test_page(test_slugfield="test-content")
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_slugfield", "tester-le-contenu")],
        )

        self.assertEqual(translated_page.test_slugfield, "tester-le-contenu")

    def test_urlfield(self):
        page = make_test_page(test_urlfield="http://test-content.com/foo")
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_urlfield", "http://test-content.fr/foo")],
        )

        self.assertEqual(translated_page.test_urlfield, "http://test-content.fr/foo")

    def test_richtextfield(self):
        page = make_test_page(test_richtextfield=RICH_TEXT_TEST_INPUT)
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                segment.wrap("test_richtextfield")
                for segment in RICH_TEXT_TEST_FRENCH_SEGMENTS
            ],
        )

        self.assertEqual(translated_page.test_richtextfield, RICH_TEXT_TEST_OUTPUT)

    def test_snippet(self):
        test_snippet = TestSnippet.objects.create(field="Test content")
        translated_snippet = test_snippet.copy_for_translation(self.locale)
        translated_snippet.save()

        # Ingest segments into the snippet
        ingest_segments(
            test_snippet,
            translated_snippet,
            self.src_locale,
            self.locale,
            [StringSegmentValue("field", "Tester le contenu")],
        )

        translated_snippet.save()

        self.assertEqual(translated_snippet.field, "Tester le contenu")

        # Now ingest a RelatedObjectSegmentValue into the page
        page = make_test_page(test_snippet=test_snippet)
        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [RelatedObjectSegmentValue.from_instance("test_snippet", test_snippet)],
        )

        # Check the translated snippet was linked to the translated page
        self.assertNotEqual(page.test_snippet_id, translated_page.test_snippet_id)
        self.assertEqual(page.test_snippet.locale, self.src_locale)
        self.assertEqual(translated_page.test_snippet.locale, self.locale)
        self.assertEqual(
            page.test_snippet.translation_key,
            translated_page.test_snippet.translation_key,
        )

        self.assertEqual(translated_page.test_snippet.field, "Tester le contenu")

    def test_childobjects(self):
        page = make_test_page()
        page.test_childobjects.add(TestChildObject(field="Test content"))
        page.save()

        child_translation_key = TestChildObject.objects.get().translation_key

        translated_page = page.copy_for_translation(self.locale)

        copy_synchronised_fields(page, translated_page)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_childobjects.{child_translation_key}.field",
                    "Tester le contenu",
                )
            ],
        )

        old_child_object = page.test_childobjects.get()
        new_child_object = translated_page.test_childobjects.get()

        self.assertNotEqual(old_child_object.id, new_child_object.id)
        self.assertEqual(old_child_object.locale, self.src_locale)
        self.assertEqual(new_child_object.locale, self.locale)
        self.assertEqual(
            old_child_object.translation_key, new_child_object.translation_key
        )

        self.assertEqual(new_child_object.field, "Tester le contenu")

    def test_customfield(self):
        page = make_test_page(test_customfield="Test content")

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue("test_customfield.foo", "Tester le contenu")],
        )

        self.assertEqual(translated_page.test_customfield, "Tester le contenu")


def make_test_page_with_streamfield_block(block_id, block_type, block_value, **kwargs):
    stream_data = [{"id": block_id, "type": block_type, "value": block_value}]

    return make_test_page(
        test_streamfield=StreamValue(
            TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
        ),
        **kwargs,
    )


class TestSegmentIngestionWithStreamField(TestCase):
    def setUp(self):
        self.src_locale = Locale.get_default()
        self.locale = Locale.objects.create(language_code="fr")

    def test_charblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_charblock", "Test content"
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Tester le contenu")],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_charblock",
                    "value": "Tester le contenu",
                }
            ],
        )

    def test_textblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_textblock", "Test content"
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Tester le contenu")],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_textblock",
                    "value": "Tester le contenu",
                }
            ],
        )

    def test_emailblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_emailblock", "test@example.com"
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue(f"test_streamfield.{block_id}", "test@example.fr")],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_emailblock",
                    "value": "test@example.fr",
                }
            ],
        )

    def test_urlblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_urlblock", "http://test-content.com/foo"
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}", "http://test-content.fr/foo"
                )
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_urlblock",
                    "value": "http://test-content.fr/foo",
                }
            ],
        )

    def test_richtextblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_richtextblock", RICH_TEXT_TEST_INPUT
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                segment.wrap(f"test_streamfield.{block_id}")
                for segment in RICH_TEXT_TEST_FRENCH_SEGMENTS
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_richtextblock",
                    "value": RICH_TEXT_TEST_OUTPUT,
                }
            ],
        )

    @unittest.expectedFailure  # Not supported
    def test_rawhtmlblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_rawhtmlblock", RICH_TEXT_TEST_INPUT
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                segment.wrap(f"test_streamfield.{block_id}")
                for segment in RICH_TEXT_TEST_FRENCH_SEGMENTS
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_rawhtmlblock",
                    "value": RICH_TEXT_TEST_OUTPUT,
                }
            ],
        )

    def test_blockquoteblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_blockquoteblock", "Test content"
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Tester le contenu")],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_blockquoteblock",
                    "value": "Tester le contenu",
                }
            ],
        )

    def test_structblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblock",
            {"field_a": "Test content", "field_b": "Some more test content"},
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_a", "Tester le contenu"
                ),
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_b", "Encore du contenu de test"
                ),
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_structblock",
                    "value": {
                        "field_a": "Tester le contenu",
                        "field_b": "Encore du contenu de test",
                    },
                }
            ],
        )

    @unittest.expectedFailure  # Not supported (probably won't ever be due to lack of path stability)
    def test_listblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_listblock", ["Test content", "Some more test content"]
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}", "Tester le contenu", order=0
                ),
                StringSegmentValue(
                    f"test_streamfield.{block_id}", "Encore du contenu de test", order=1
                ),
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_listblock",
                    "value": ["Tester le contenu", "Encore du contenu de test"],
                }
            ],
        )

    def test_nestedstreamblock(self):
        block_id = uuid.uuid4()
        nested_block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_nestedstreamblock",
            [{"id": str(nested_block_id), "type": "block_a", "value": "Test content"}],
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.{nested_block_id}",
                    "Tester le contenu",
                )
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_nestedstreamblock",
                    "value": [
                        {
                            "id": str(nested_block_id),
                            "type": "block_a",
                            "value": "Tester le contenu",
                        }
                    ],
                }
            ],
        )

    def test_customstructblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customstructblock",
            {"field_a": "Test content", "field_b": "Some more test content"},
        )

        translated_page = page.copy_for_translation(self.locale)

        ingest_segments(
            page,
            translated_page,
            self.src_locale,
            self.locale,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.foo",
                    "Tester le contenu / Encore du contenu de test",
                )
            ],
        )

        translated_page.save()
        translated_page.refresh_from_db()

        self.assertEqual(
            translated_page.test_streamfield.stream_data,
            [
                {
                    "id": str(block_id),
                    "type": "test_customstructblock",
                    "value": {
                        "field_a": "Tester le contenu",
                        "field_b": "Encore du contenu de test",
                    },
                }
            ],
        )
