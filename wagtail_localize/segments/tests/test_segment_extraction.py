import uuid
import unittest

from django.test import TestCase

from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page

from wagtail_localize.segments import (
    StringSegmentValue,
    TemplateSegmentValue,
    RelatedObjectSegmentValue,
)
from wagtail_localize.segments.extract import extract_segments
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import (
    TestPage,
    TestSnippet,
    TestChildObject,
    TestNonParentalChildObject,
)


def make_test_page(**kwargs):
    root_page = Page.objects.get(id=1)
    kwargs.setdefault("title", "Test page")
    return root_page.add_child(instance=TestPage(**kwargs))


RICH_TEXT_TEST_INPUT = '<h1>This is a heading</h1><p>This is a paragraph. &lt;foo&gt; <b>Bold text</b></p><ul><li><a href="http://example.com">This is a link</a>.</li></ul>'

RICH_TEXT_TEST_OUTPUT = [
    TemplateSegmentValue(
        "",
        "html",
        '<h1><text position="0"></text></h1><p><text position="1"></text></p><ul><li><text position="2"></text></li></ul>',
        3,
    ),
    StringSegmentValue("", "This is a heading"),
    StringSegmentValue.from_source_html(
        "",
        'This is a paragraph. &lt;foo&gt; <b>Bold text</b>',
    ),
    StringSegmentValue(
        "",
        StringValue('<a id="a1">This is a link</a>.'),
        attrs={
            "a1": {"href": "http://example.com"}
        }
    ),
]


class TestSegmentExtraction(TestCase):
    def test_charfield(self):
        page = make_test_page(test_charfield="Test content")
        segments = extract_segments(page)

        self.assertEqual(segments, [StringSegmentValue("test_charfield", "Test content")])

    def test_null_charfield(self):
        page = make_test_page(test_charfield=None)
        segments = extract_segments(page)

        self.assertEqual(segments, [])

    def test_textfield(self):
        page = make_test_page(test_textfield="Test content")
        segments = extract_segments(page)

        self.assertEqual(segments, [StringSegmentValue("test_textfield", "Test content")])

    def test_emailfield(self):
        page = make_test_page(test_emailfield="test@example.com")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_emailfield", "test@example.com")]
        )

    def test_slugfield(self):
        page = make_test_page(test_slugfield="test-content")
        segments = extract_segments(page)

        self.assertEqual(segments, [StringSegmentValue("test_slugfield", "test-content")])

    def test_urlfield(self):
        page = make_test_page(test_urlfield="http://test-content.com/foo")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_urlfield", "http://test-content.com/foo")]
        )

    def test_richtextfield(self):
        page = make_test_page(test_richtextfield=RICH_TEXT_TEST_INPUT)
        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [segment.wrap("test_richtextfield") for segment in RICH_TEXT_TEST_OUTPUT],
        )

    def test_snippet(self):
        test_snippet = TestSnippet.objects.create(field="Test content")
        page = make_test_page(test_snippet=test_snippet)
        segments = extract_segments(page)

        self.assertEqual(
            segments, [RelatedObjectSegmentValue.from_instance("test_snippet", test_snippet)]
        )

    def test_childobjects(self):
        page = make_test_page()
        page.test_childobjects.add(TestChildObject(field="Test content"))
        page.save()

        child_translation_key = TestChildObject.objects.get().translation_key

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_childobjects.{child_translation_key}.field", "Test content"
                )
            ],
        )

    def test_nonparentalchildobjects(self):
        page = make_test_page()
        page.save()
        TestNonParentalChildObject.objects.create(page=page, field="Test content")

        segments = extract_segments(page)

        # No segments this time as we don't extract ManyToOneRel's that don't use ParentalKeys
        self.assertEqual(segments, [])

    def test_customfield(self):
        page = make_test_page(test_customfield="Test content")

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [StringSegmentValue("test_customfield.foo", "Test content and some extra")],
        )


def make_test_page_with_streamfield_block(block_id, block_type, block_value, **kwargs):
    stream_data = [{"id": block_id, "type": block_type, "value": block_value}]

    return make_test_page(
        test_streamfield=StreamValue(
            TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
        ),
        **kwargs,
    )


class TestSegmentExtractionWithStreamField(TestCase):
    def test_charblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_charblock", "Test content"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")]
        )

    def test_textblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_textblock", "Test content"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")]
        )

    @unittest.expectedFailure  # Not supported
    def test_emailblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_emailblock", "test@example.com"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue(f"test_streamfield.{block_id}", "test@example.com")]
        )

    @unittest.expectedFailure  # Not supported
    def test_urlblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_urlblock", "http://test-content.com/foo"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}", "http://test-content.com/foo"
                )
            ],
        )

    def test_richtextblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_richtextblock", RICH_TEXT_TEST_INPUT
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                segment.wrap(f"test_streamfield.{block_id}")
                for segment in RICH_TEXT_TEST_OUTPUT
            ],
        )

    @unittest.expectedFailure  # Not supported
    def test_rawhtmlblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_rawhtmlblock", RICH_TEXT_TEST_INPUT
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                segment.wrap(f"test_streamfield.{block_id}")
                for segment in RICH_TEXT_TEST_OUTPUT
            ],
        )

    def test_blockquoteblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_blockquoteblock", "Test content"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")]
        )

    def test_structblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblock",
            {"field_a": "Test content", "field_b": "Some more test content"},
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(f"test_streamfield.{block_id}.field_a", "Test content"),
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_b", "Some more test content"
                ),
            ],
        )

    @unittest.expectedFailure  # Not supported (probably won't ever be due to lack of path stability)
    def test_listblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_listblock", ["Test content", "Some more test content"]
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(f"test_streamfield.{block_id}", "Test content"),
                StringSegmentValue(f"test_streamfield.{block_id}", "Some more test content"),
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

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.{nested_block_id}", "Test content"
                )
            ],
        )

    def test_customstructblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customstructblock",
            {"field_a": "Test content", "field_b": "Some more test content"},
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.foo",
                    "Test content / Some more test content",
                )
            ],
        )

    def test_customblockwithoutextractmethod(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customblockwithoutextractmethod",
            {},
        )

        segments = extract_segments(page)
        self.assertEqual(segments, [])
