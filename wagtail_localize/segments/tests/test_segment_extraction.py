import unittest
import uuid

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Site

from wagtail_localize.segments import (
    OverridableSegmentValue,
    RelatedObjectSegmentValue,
    StringSegmentValue,
    TemplateSegmentValue,
)
from wagtail_localize.segments.extract import (
    StreamFieldSegmentExtractor,
    extract_segments,
)
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import (
    TestChildObject,
    TestModelWithInvalidForeignKey,
    TestNonParentalChildObject,
    TestPage,
    TestSnippet,
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
        "This is a paragraph. &lt;foo&gt; <b>Bold text</b>",
    ),
    StringSegmentValue(
        "",
        StringValue('<a id="a1">This is a link</a>.'),
        attrs={"a1": {"href": "http://example.com"}},
    ),
    OverridableSegmentValue("'http://example.com'", "http://example.com"),
]


class TestSegmentExtraction(TestCase):
    def test_charfield(self):
        page = make_test_page(test_charfield="Test content")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_charfield", "Test content")]
        )

    def test_null_charfield(self):
        page = make_test_page(test_charfield=None)
        segments = extract_segments(page)

        self.assertEqual(segments, [])

    def test_textfield(self):
        page = make_test_page(test_textfield="Test content")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_textfield", "Test content")]
        )

    def test_emailfield(self):
        page = make_test_page(test_emailfield="test@example.com")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_emailfield", "test@example.com")]
        )

    def test_slugfield(self):
        page = make_test_page(test_slugfield="test-content")
        segments = extract_segments(page)

        self.assertEqual(
            segments, [StringSegmentValue("test_slugfield", "test-content")]
        )

    def test_urlfield(self):
        page = make_test_page(test_urlfield="http://test-content.com/foo")
        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [StringSegmentValue("test_urlfield", "http://test-content.com/foo")],
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
            segments,
            [RelatedObjectSegmentValue.from_instance("test_snippet", test_snippet)],
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

    def test_synchronised_textfield(self):
        page = make_test_page(test_synchronized_textfield="Test content")

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [OverridableSegmentValue("test_synchronized_textfield", "Test content")],
        )

    def test_non_overridable_synchronised_textfield(self):
        page = make_test_page(
            test_not_overridable_synchronized_textfield="Test content"
        )

        segments = extract_segments(page)

        # Shouldn't extract any segments as this isn't overridable
        self.assertEqual(segments, [])


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
            segments,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")],
        )

    def test_textblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_textblock", "Test content"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")],
        )

    @unittest.expectedFailure  # Not supported
    def test_emailblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_emailblock", "test@example.com"
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [StringSegmentValue(f"test_streamfield.{block_id}", "test@example.com")],
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

    def test_embedblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_embedblock",
            "https://www.youtube.com/watch?v=aBByJQCaaEA",
        )

        segments = extract_segments(page)

        self.assertEqual(
            segments,
            [
                OverridableSegmentValue(
                    f"test_streamfield.{block_id}",
                    "https://www.youtube.com/watch?v=aBByJQCaaEA",
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
            segments,
            [StringSegmentValue(f"test_streamfield.{block_id}", "Test content")],
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
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_a", "Test content"
                ),
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_b", "Some more test content"
                ),
            ],
        )

    @unittest.skipUnless(
        WAGTAIL_VERSION >= (2, 16),
        "ListBlocks are supported starting with Wagtail 2.16",
    )
    def test_listblock(self):
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_listblock",
            [
                {
                    "type": "item",
                    "value": "Test content",
                    "id": "11111111-1111-1111-1111-111111111111",
                },
                {
                    "type": "item",
                    "value": "Some more test content",
                    "id": "22222222-2222-2222-2222-222222222222",
                },
            ],
        )

        expected_segments = [
            StringSegmentValue(f"test_streamfield.{block_id}.{item.id}", item.value)
            for item in page.test_streamfield[0].value.bound_blocks
        ]
        segments = extract_segments(page)
        self.assertEqual(segments, expected_segments)

    @unittest.skipUnless(
        WAGTAIL_VERSION >= (2, 16),
        "ListBlocks are supported starting with Wagtail 2.16",
    )
    def test_listblock_not_extracted_when_not_in_block_format(self):
        page = make_test_page_with_streamfield_block(
            uuid.uuid4(), "test_listblock", ["Test content", "Some more test content"]
        )
        segments = StreamFieldSegmentExtractor(
            page.test_streamfield
        ).handle_stream_block(page.test_streamfield)
        self.assertEqual(segments, [])

    @unittest.skipUnless(
        WAGTAIL_VERSION >= (2, 16),
        "ListBlocks are supported starting with Wagtail 2.16",
    )
    def test_listblock_in_structblock(self):
        block_id = uuid.uuid4()
        item_one_id = "11111111-1111-1111-1111-111111111111"
        item_two_id = "22222222-2222-2222-2222-222222222222"
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_listblock_in_structblock",
            {
                "title": "Nested",
                "items": [
                    {
                        "type": "item",
                        "value": "Test content",
                        "id": item_one_id,
                    },
                    {
                        "type": "item",
                        "value": "Some more test content",
                        "id": item_two_id,
                    },
                ],
            },
        )

        segments = extract_segments(page)
        expected_segments = [
            StringSegmentValue(f"test_streamfield.{block_id}.title", "Nested"),
            StringSegmentValue(
                f"test_streamfield.{block_id}.items.{item_one_id}", "Test content"
            ),
            StringSegmentValue(
                f"test_streamfield.{block_id}.items.{item_two_id}",
                "Some more test content",
            ),
        ]

        self.assertEqual(segments, expected_segments)

    @unittest.skipUnless(
        WAGTAIL_VERSION >= (2, 16),
        "ListBlocks are supported starting with Wagtail 2.16",
    )
    def test_listblock_in_nestedstreamblock(self):
        block_id = uuid.uuid4()
        nested_block_id = uuid.uuid4()
        item_id = "11111111-1111-1111-1111-111111111111"
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_nestedstreamblock",
            [
                {
                    "id": str(nested_block_id),
                    "type": "block_l",
                    "value": [
                        {
                            "type": "item",
                            "value": "Test content",
                            "id": item_id,
                        }
                    ],
                },
            ],
        )

        segments = extract_segments(page)
        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.{nested_block_id}.{item_id}",
                    "Test content",
                )
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

    def test_invalid_foreign_key(self):
        instance = TestModelWithInvalidForeignKey.objects.create(fk=Site.objects.get())

        with self.assertRaises(ImproperlyConfigured) as e:
            extract_segments(instance)

        self.assertEqual(
            str(e.exception),
            "The foreign key `wagtail_localize_test.TestModelWithInvalidForeignKey.fk` "
            "was registered as a translatable field but the model it points to "
            "`wagtailcore.Site` is not translatable",
        )
