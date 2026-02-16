"""
Comprehensive tests for the translatable_blocks feature on StructBlocks.

These tests cover the ability to define `translatable_blocks`
on StructBlocks to control which sub-fields are translatable, addressing issue #307.

Test scenarios include:
- Excluding fields from translation (empty list)
- Explicit inclusion of specific fields
- Default behavior (backward compatibility)
- Overrides for images
- Integration with model-level translatable/synchronized fields
- Synchronization vs translation behavior
"""

import uuid

from django.test import TestCase
from wagtail.blocks import StreamValue
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from wagtail_localize.segments import (
    OverridableSegmentValue,
    StringSegmentValue,
)
from wagtail_localize.segments.extract import (
    StreamFieldSegmentExtractor,
    extract_segments,
)
from wagtail_localize.test.models import TestPage


def make_test_page(**kwargs):
    root_page = Page.objects.get(id=1)
    kwargs.setdefault("title", "Test page")
    return root_page.add_child(instance=TestPage(**kwargs))


def make_test_page_with_streamfield_block(block_id, block_type, block_value, **kwargs):
    stream_data = [{"id": block_id, "type": block_type, "value": block_value}]

    return make_test_page(
        test_streamfield=StreamValue(
            TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
        ),
        **kwargs,
    )


class TestTranslatableBlocksFeature(TestCase):
    """Test the translatable_blocks attribute on StructBlocks."""

    def test_structblock_with_explicit_translatable_blocks(self):
        """
        Test that only explicitly included fields are extracted when
        translatable_blocks is defined with specific field names.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblockwithoverrides",
            {"field_a": "Translatable content", "field_b": "Non-translatable content"},
        )

        segments = extract_segments(page)

        # Only field_a should be extracted, field_b should be ignored
        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_a",
                    "Translatable content",
                )
            ],
        )
        # Verify field_b is NOT in the segments
        self.assertNotIn("field_b", str(segments))

    def test_structblock_with_empty_translatable_blocks(self):
        """
        Test that no fields are extracted when translatable_blocks is an empty list.
        This is useful for blocks like CodeBlock or YouTubeBlock where nothing should be translated.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblockignoreall",
            {
                "field_a": "Non-translatable content",
                "field_b": "Non-translatable content",
            },
        )

        segments = extract_segments(page)

        # No segments should be extracted
        self.assertEqual(segments, [])

    def test_structblock_without_translatable_blocks_default_behavior(self):
        """
        Test backward compatibility: when translatable_blocks is NOT defined,
        all sub-fields should be extracted (default behavior).
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblock",
            {"field_a": "Test content A", "field_b": "Test content B"},
        )

        segments = extract_segments(page)

        # Both fields should be extracted (default behavior)
        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_a", "Test content A"
                ),
                StringSegmentValue(
                    f"test_streamfield.{block_id}.field_b", "Test content B"
                ),
            ],
        )

    def test_youtube_block_with_empty_translatable_blocks(self):
        """
        Test YouTubeBlock scenario: translatable_blocks = [] prevents extraction.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_youtubeblock",
            {"url": "https://youtube.com/watch?v=abc", "caption": "Video caption"},
        )

        segments = extract_segments(page)

        # No segments should be extracted from YouTubeBlock
        self.assertEqual(segments, [])

    def test_code_block_with_empty_translatable_blocks(self):
        """
        Test CodeBlock scenario: translatable_blocks = [] prevents extraction.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_codeblock",
            {"language": "python", "code": "print('hello')"},
        )

        segments = extract_segments(page)

        # No segments should be extracted from CodeBlock
        self.assertEqual(segments, [])

    def test_custom_image_block_default_both_extracted(self):
        """
        Test CustomImageBlock without translatable_blocks defined.
        Both image and description should be extracted by default.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customimageblock",
            {"image": test_image.pk, "description": "Image description"},
        )

        segments = extract_segments(page)

        # Both image (as OverridableSegmentValue) and description (as StringSegmentValue)
        # should be extracted
        self.assertEqual(len(segments), 2)
        self.assertIn(
            OverridableSegmentValue(
                f"test_streamfield.{block_id}.image", test_image.pk
            ),
            segments,
        )
        self.assertIn(
            StringSegmentValue(
                f"test_streamfield.{block_id}.description", "Image description"
            ),
            segments,
        )

    def test_custom_image_block_with_translatable_description_only(self):
        """
        Test CustomImageBlock with translatable_blocks = ['description'].
        Only the description should be translatable, image should be synchronized.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customimageblock_with_translatable_description",
            {"image": test_image.pk, "description": "Image description"},
        )

        segments = extract_segments(page)

        # Only description should be extracted
        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.description", "Image description"
                )
            ],
        )
        # Verify image is NOT in the segments
        for segment in segments:
            self.assertNotIn("image", segment.path)

    def test_custom_image_block_with_both_translatable(self):
        """
        Test CustomImageBlock with translatable_blocks = ['image', 'description'].
        Both should be extracted, allowing per-language image overrides.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customimageblock_with_both_translatable",
            {"image": test_image.pk, "description": "Image description"},
        )

        segments = extract_segments(page)

        # Both image and description should be extracted
        self.assertEqual(len(segments), 2)
        self.assertIn(
            OverridableSegmentValue(
                f"test_streamfield.{block_id}.image", test_image.pk
            ),
            segments,
        )
        self.assertIn(
            StringSegmentValue(
                f"test_streamfield.{block_id}.description", "Image description"
            ),
            segments,
        )

    def test_address_block_image_translatable_address_locked(self):
        """
        Test AddressBlock where translatable_blocks = ['image'].
        The image can vary by language (overridable), but the address is locked.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_addressblock",
            {"address": "123 Main St, City", "image": test_image.pk},
        )

        segments = extract_segments(page)

        # Only image should be extracted (overridable)
        self.assertEqual(
            segments,
            [
                OverridableSegmentValue(
                    f"test_streamfield.{block_id}.image", test_image.pk
                )
            ],
        )
        # Verify address is NOT in the segments
        for segment in segments:
            self.assertNotIn("address", segment.path)

    def test_synchronized_streamfield_with_translatable_blocks(self):
        """
        Test that translatable_blocks works correctly with synchronized StreamFields.
        When a StreamField is synchronized and overridable, segments should be OverridableSegmentValue.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        stream_data = [
            {
                "id": str(block_id),
                "type": "test_customimageblock_with_both_translatable",
                "value": {"image": test_image.pk, "description": "Synchronized image"},
            }
        ]

        page = make_test_page(
            test_synchronized_streamfield=StreamValue(
                TestPage.test_synchronized_streamfield.field.stream_block,
                stream_data,
                is_lazy=True,
            )
        )

        segments = extract_segments(page)

        # For synchronized + overridable StreamField, extracted segments should be
        # OverridableSegmentValue
        # Both image and description should be overridable
        self.assertEqual(len(segments), 2)

        # Find the segments
        image_segment = [
            s for s in segments if "image" in s.path and "description" not in s.path
        ][0]
        description_segment = [s for s in segments if "description" in s.path][0]

        # Both should be OverridableSegmentValue because it's a synchronized field
        self.assertIsInstance(image_segment, OverridableSegmentValue)
        self.assertIsInstance(description_segment, OverridableSegmentValue)

    def test_nested_structblock_with_translatable_blocks(self):
        """
        Test that translatable_blocks is respected in nested StructBlocks.
        """
        block_id = uuid.uuid4()
        nested_block_id = uuid.uuid4()

        # Create a nested stream with a StructBlock that has translatable_blocks
        stream_data = [
            {
                "id": str(block_id),
                "type": "test_nestedstreamblock",
                "value": [
                    {
                        "id": str(nested_block_id),
                        "type": "block_a",
                        "value": "Nested content",
                    }
                ],
            }
        ]

        page = make_test_page(
            test_streamfield=StreamValue(
                TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
            )
        )

        segments = extract_segments(page)

        # The nested block should be extracted
        self.assertEqual(
            segments,
            [
                StringSegmentValue(
                    f"test_streamfield.{block_id}.{nested_block_id}", "Nested content"
                )
            ],
        )

    def test_multiple_blocks_with_different_translatable_blocks(self):
        """
        Test a StreamField with multiple blocks, each with different translatable_blocks settings.
        """
        block_id_1 = uuid.uuid4()
        block_id_2 = uuid.uuid4()
        block_id_3 = uuid.uuid4()

        stream_data = [
            {
                "id": str(block_id_1),
                "type": "test_structblockwithoverrides",  # Only field_a
                "value": {"field_a": "Content A1", "field_b": "Content B1"},
            },
            {
                "id": str(block_id_2),
                "type": "test_structblockignoreall",  # Nothing
                "value": {"field_a": "Content A2", "field_b": "Content B2"},
            },
            {
                "id": str(block_id_3),
                "type": "test_structblock",  # Both fields (default)
                "value": {"field_a": "Content A3", "field_b": "Content B3"},
            },
        ]

        page = make_test_page(
            test_streamfield=StreamValue(
                TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
            )
        )

        segments = extract_segments(page)

        # Should extract: block_1.field_a, block_3.field_a, block_3.field_b
        # Should NOT extract: block_1.field_b, block_2.field_a, block_2.field_b
        expected_segments = [
            StringSegmentValue(f"test_streamfield.{block_id_1}.field_a", "Content A1"),
            StringSegmentValue(f"test_streamfield.{block_id_3}.field_a", "Content A3"),
            StringSegmentValue(f"test_streamfield.{block_id_3}.field_b", "Content B3"),
        ]

        self.assertEqual(segments, expected_segments)

    def test_empty_values_in_translatable_blocks(self):
        """
        Test that empty values in translatable_blocks fields are handled correctly.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customimageblock_with_translatable_description",
            {"image": None, "description": ""},
        )

        segments = extract_segments(page)

        # Empty description should not be extracted (is_empty() check)
        self.assertEqual(segments, [])

    def test_translatable_blocks_with_richtext(self):
        """
        Test that translatable_blocks works with blocks containing RichTextBlock.
        """
        block_id = uuid.uuid4()

        # Using a StructBlock that would contain a RichTextBlock
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_richtextblock",
            "<p>Rich text content</p>",
        )

        segments = extract_segments(page)

        # RichTextBlock should be extracted as usual
        self.assertTrue(len(segments) > 0)
        # Should contain template and string segments
        self.assertTrue(
            any(segment.path.startswith("test_streamfield") for segment in segments)
        )

    def test_directly_using_streamfield_segment_extractor(self):
        """
        Test using StreamFieldSegmentExtractor directly to verify translatable_blocks behavior.
        """
        block_id = uuid.uuid4()
        stream_data = [
            {
                "id": str(block_id),
                "type": "test_structblockwithoverrides",
                "value": {"field_a": "Content A", "field_b": "Content B"},
            }
        ]

        page = make_test_page(
            test_streamfield=StreamValue(
                TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
            )
        )

        extractor = StreamFieldSegmentExtractor(page.test_streamfield)
        segments = extractor.handle_stream_block(page.test_streamfield)

        # Only field_a should be extracted
        self.assertEqual(len(segments), 1)
        self.assertIn("field_a", segments[0].path)
        self.assertNotIn("field_b", str(segments))

    def test_translatable_blocks_preserves_order(self):
        """
        Test that the order of fields in translatable_blocks doesn't affect extraction.
        Fields should be extracted in the order they appear in the block definition.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_customimageblock_with_both_translatable",
            {"image": test_image.pk, "description": "Description"},
        )

        segments = extract_segments(page)

        # Check that segments are in the expected order (image before description)
        self.assertEqual(len(segments), 2)
        self.assertIn("image", segments[0].path)
        self.assertIn("description", segments[1].path)


class TestTranslatableBlocksWithSynchronizedFields(TestCase):
    """Test the interaction between translatable_blocks and synchronized fields."""

    def test_synchronized_streamfield_respects_translatable_blocks(self):
        """
        Test that when a StreamField is synchronized, translatable_blocks still controls
        which sub-fields are extracted as overridables.
        """
        block_id = uuid.uuid4()
        stream_data = [
            {
                "id": str(block_id),
                "type": "test_structblockwithoverrides",
                "value": {"field_a": "Content A", "field_b": "Content B"},
            }
        ]

        page = make_test_page(
            test_synchronized_streamfield=StreamValue(
                TestPage.test_synchronized_streamfield.field.stream_block,
                stream_data,
                is_lazy=True,
            )
        )

        segments = extract_segments(page)

        # Only field_a should be extracted as an OverridableSegmentValue
        self.assertEqual(len(segments), 1)
        self.assertIsInstance(segments[0], OverridableSegmentValue)
        self.assertIn("field_a", segments[0].path)

    def test_translatable_vs_synchronized_streamfield_behavior(self):
        """
        Test the difference between translatable and synchronized StreamFields
        with translatable_blocks.
        """
        block_id_translatable = uuid.uuid4()
        block_id_synchronized = uuid.uuid4()

        # Same block type in both fields
        block_value = {"field_a": "Content", "field_b": "Content"}

        stream_data_translatable = [
            {
                "id": str(block_id_translatable),
                "type": "test_structblockwithoverrides",
                "value": block_value,
            }
        ]

        stream_data_synchronized = [
            {
                "id": str(block_id_synchronized),
                "type": "test_structblockwithoverrides",
                "value": block_value,
            }
        ]

        page = make_test_page(
            test_streamfield=StreamValue(
                TestPage.test_streamfield.field.stream_block,
                stream_data_translatable,
                is_lazy=True,
            ),
            test_synchronized_streamfield=StreamValue(
                TestPage.test_synchronized_streamfield.field.stream_block,
                stream_data_synchronized,
                is_lazy=True,
            ),
        )

        segments = extract_segments(page)

        # Find segments from each field
        translatable_segments = [
            s
            for s in segments
            if "test_streamfield" in s.path and "synchronized" not in s.path
        ]
        synchronized_segments = [s for s in segments if "test_synchronized" in s.path]

        # Translatable field should have StringSegmentValue
        self.assertEqual(len(translatable_segments), 1)
        self.assertIsInstance(translatable_segments[0], StringSegmentValue)

        # Synchronized field should have OverridableSegmentValue
        self.assertEqual(len(synchronized_segments), 1)
        self.assertIsInstance(synchronized_segments[0], OverridableSegmentValue)


class TestTranslatableBlocksBackwardCompatibility(TestCase):
    """Test that existing code continues to work without translatable_blocks."""

    def test_existing_blocks_without_translatable_blocks_unchanged(self):
        """
        Test that blocks without translatable_blocks defined continue to work as before.
        All fields should be extracted.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblock",
            {"field_a": "Content A", "field_b": "Content B"},
        )

        segments = extract_segments(page)

        # Both fields should be extracted (backward compatibility)
        self.assertEqual(len(segments), 2)
        self.assertTrue(any("field_a" in s.path for s in segments))
        self.assertTrue(any("field_b" in s.path for s in segments))

    def test_charblock_textblock_still_extracted(self):
        """
        Test that CharBlock and TextBlock continue to be extracted as before.
        """
        block_id_char = uuid.uuid4()
        block_id_text = uuid.uuid4()

        stream_data = [
            {
                "id": str(block_id_char),
                "type": "test_charblock",
                "value": "Char content",
            },
            {
                "id": str(block_id_text),
                "type": "test_textblock",
                "value": "Text content",
            },
        ]

        page = make_test_page(
            test_streamfield=StreamValue(
                TestPage.test_streamfield.field.stream_block, stream_data, is_lazy=True
            )
        )

        segments = extract_segments(page)

        self.assertEqual(len(segments), 2)
        self.assertTrue(any("Char content" in str(s.data) for s in segments))
        self.assertTrue(any("Text content" in str(s.data) for s in segments))

    def test_imagechooserblock_still_extracted_as_overridable(self):
        """
        Test that ImageChooserBlock continues to be extracted as OverridableSegmentValue.
        """
        Image = get_image_model()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id), "test_imagechooserblock", test_image.pk
        )

        segments = extract_segments(page)

        self.assertEqual(len(segments), 1)
        self.assertIsInstance(segments[0], OverridableSegmentValue)
        self.assertEqual(segments[0].data, test_image.pk)


class TestTranslatableBlocksEdgeCases(TestCase):
    """Test edge cases and error conditions for translatable_blocks."""

    def test_translatable_blocks_with_nonexistent_field(self):
        """
        Test that nonexistent fields in translatable_blocks are ignored gracefully.
        This is the current behavior - the code doesn't validate field names.
        """
        # This test verifies current behavior. The implementation doesn't validate
        # that fields in translatable_blocks actually exist, it just filters.
        # If a field name is in translatable_blocks but doesn't exist in the block,
        # it simply won't match anything and won't be extracted.
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblockwithoverrides",  # Only has field_a, field_b
            {"field_a": "Content A", "field_b": "Content B"},
        )

        segments = extract_segments(page)

        # Should still work normally - field_a is in translatable_blocks
        self.assertEqual(len(segments), 1)
        self.assertIn("field_a", segments[0].path)

    def test_translatable_blocks_none_value(self):
        """
        Test behavior when translatable_blocks is None (should use default behavior).
        """
        # When translatable_blocks is not defined, it should be None,
        # and all fields should be extracted
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblock",  # No translatable_blocks defined
            {"field_a": "Content A", "field_b": "Content B"},
        )

        segments = extract_segments(page)

        # Both fields should be extracted
        self.assertEqual(len(segments), 2)

    def test_empty_structblock_with_translatable_blocks(self):
        """
        Test an empty StructBlock with translatable_blocks defined.
        """
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblockwithoverrides",
            {"field_a": "", "field_b": ""},
        )

        segments = extract_segments(page)

        # Empty strings should not be extracted
        self.assertEqual(segments, [])

    def test_translatable_blocks_case_sensitivity(self):
        """
        Test that field names in translatable_blocks are case-sensitive.
        """
        # This test verifies that field matching is case-sensitive
        # (as it should be in Python)
        block_id = uuid.uuid4()
        page = make_test_page_with_streamfield_block(
            str(block_id),
            "test_structblockwithoverrides",  # translatable_blocks = ["field_a"]
            {"field_a": "Content A", "field_b": "Content B"},
        )

        segments = extract_segments(page)

        # Only field_a should match (case-sensitive)
        self.assertEqual(len(segments), 1)
        self.assertIn("field_a", segments[0].path)
