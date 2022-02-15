from collections import defaultdict

from django.apps import apps
from django.db import models
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.rich_text import RichText

from wagtail_localize.strings import restore_strings

from .types import OverridableSegmentValue, StringSegmentValue


def unquote_path_component(text):
    """
    Removes quotes around a quoted path component, and unescapes any special characters.
    """
    if text[0] != "'" or text[-1] != "'":
        raise ValueError("value must be a quoted string")

    return text[1:-1].replace("\\'", "'").replace("\\\\", "\\")


def organise_template_segments(segments):
    """
    Organises the segments for a RichTextField or RichTextBlock to prepare them for recombining.

    This takes a single TemplateValue segment, and zero or more StringValueSegments/OverridableValueSegments.
    It detects the TemplateValue and groups the OverridableValueSegments with their StringValueSegments.

    Arguments:
        segments (list[StringValueSegment, TemplateValueSegment, or OverridableValueSegment]): The segments to organise.

    Returns:
        tuple[string, string, list[tuple[string, dict]]]: Returns a 3-tuple. The first component is the template format,
            the second component is the template itself as a string, the third component is a list of 2-tuples that
            represent translated strings to be reinserted into the template. These 2-tuples contain the string itself
            and a dict of HTML attributes to insert back into the string.
    """
    # The first segment is always the template, followed by the texts in order of their position

    segments.sort(key=lambda segment: segment.order)
    template = segments[0]
    xrefs = {
        unquote_path_component(segment.path): segment.data
        for segment in segments
        if isinstance(segment, OverridableSegmentValue) and segment.data
    }

    def translate_href(attrs):
        """Update href in segments with their translated values."""
        if attrs:
            for val in attrs.values():
                if val and "href" in val and val["href"] in xrefs:
                    val["href"] = xrefs[val["href"]]
        return attrs

    return (
        template.format,
        template.template,
        [
            (segment.string, translate_href(segment.attrs))
            for segment in segments[1:]
            if isinstance(segment, StringSegmentValue)
        ],
    )


def handle_related_object(related_model, src_locale, tgt_locale, segments):
    """
    Returns the instance of the related object that is referenced by the given segments.

    This is called when inserting segments into a ForeignKey or ChooserBlock.

    Raises:
        Model.DoesNotExist: If the segment is a RelatedObjectValue and the related object doesn't exist in the target locale.
        Model.DoesNotExist: If the segment is a OverridableSegmentValue and the referenced instance no longer exists.

    Returns:
        Model: The referenced instance.
    """
    if len(segments) > 1:
        raise ValueError(
            "Related object field can only have a single segment. Found {}".format(
                len(segments)
            )
        )

    segment = segments[0]

    if isinstance(segment, OverridableSegmentValue):
        return related_model.objects.get(pk=segment.data)

    else:
        # Assume it's a RelatedObjectValue
        return segment.get_instance(tgt_locale)


class StreamFieldSegmentsWriter:
    """
    A helper class to help traverse StreamField values and insert translated segments.
    """

    def __init__(self, field, src_locale, tgt_locale):
        """
        Initialises a StreamFieldSegmentsWriter.

        Args:
            field (StreamField): The StreamField to extract segments from.
            src_locale (Locale): The source locale of the segments.
            tgt_locale (Locale): The locale of the segment translations.
        """
        self.field = field
        self.src_locale = src_locale
        self.tgt_locale = tgt_locale

    def handle_block(self, block_type, block_value, segments):
        # Need to check if the app is installed before importing EmbedBlock
        # See: https://github.com/wagtail/wagtail-localize/issues/309
        if apps.is_installed("wagtail.embeds"):
            from wagtail.embeds.blocks import EmbedBlock, EmbedValue

            if isinstance(block_type, EmbedBlock):
                if len(segments) > 1:
                    raise ValueError(
                        "EmbedBlock can only have a single segment. Found {}".format(
                            len(segments)
                        )
                    )

                segment = segments[0]

                if isinstance(segment, OverridableSegmentValue):
                    return EmbedValue(segment.data)

        if hasattr(block_type, "restore_translated_segments"):
            return block_type.restore_translated_segments(block_value, segments)

        elif isinstance(
            block_type,
            (blocks.CharBlock, blocks.TextBlock, blocks.URLBlock, blocks.EmailBlock),
        ):
            if len(segments) > 1:
                raise ValueError(
                    "TextBlock/CharBlock can only have a single segment. Found {}".format(
                        len(segments)
                    )
                )

            segment = segments[0]

            if isinstance(segment, OverridableSegmentValue):
                return segment.data
            else:
                # Assume it's a StringSegmentValue
                return segment.render_text()

        elif isinstance(block_type, blocks.RichTextBlock):
            format, template, strings = organise_template_segments(segments)
            assert format == "html"
            return RichText(restore_strings(template, strings))

        elif isinstance(block_type, blocks.ChooserBlock):
            return self.handle_related_object_block(block_value, segments)

        elif isinstance(block_type, blocks.StructBlock):
            return self.handle_struct_block(block_value, segments)

        elif isinstance(block_type, blocks.ListBlock):
            return self.handle_list_block(block_value, segments)

        elif isinstance(block_type, blocks.StreamBlock):
            return self.handle_stream_block(block_value, segments)

        else:
            raise Exception(
                "Unrecognised StreamField block type '{}'. Have you implemented restore_translated_segments() on this class?".format(
                    block_type.__class__.__name__
                )
            )

    def handle_related_object_block(self, related_object, segments):
        return handle_related_object(
            related_object.__class__, self.src_locale, self.tgt_locale, segments
        )

    def handle_struct_block(self, struct_block, segments):
        segments_by_field = defaultdict(list)

        for segment in segments:
            field_name, segment = segment.unwrap()
            segments_by_field[field_name].append(segment)

        for field_name, segments in segments_by_field.items():
            if segments:
                block_type = struct_block.block.child_blocks[field_name]
                block_value = struct_block[field_name]
                struct_block[field_name] = self.handle_block(
                    block_type, block_value, segments
                )

        return struct_block

    def handle_list_block(self, list_block, segments):
        if WAGTAIL_VERSION >= (2, 16):
            segments_by_block = defaultdict(list)

            for segment in segments:
                block_uuid, segment = segment.unwrap()
                segments_by_block[block_uuid].append(segment)

            for block_index, block in enumerate(list_block.bound_blocks):
                block_segments = segments_by_block[block.id]
                list_block.bound_blocks[block_index].value = self.handle_block(
                    block.block, block.value, block_segments
                )

            return list_block

    def get_stream_block_child_data(self, stream_block, block_uuid):
        for stream_child in stream_block:
            if stream_child.id == block_uuid:
                return stream_child

    def handle_stream_block(self, stream_block, segments):
        segments_by_block = defaultdict(list)

        for segment in segments:
            block_uuid, segment = segment.unwrap()
            segments_by_block[block_uuid].append(segment)

        for block_uuid, segments in segments_by_block.items():
            block = self.get_stream_block_child_data(stream_block, block_uuid)
            block.value = self.handle_block(block.block, block.value, segments)

        return stream_block


def ingest_segments(original_obj, translated_obj, src_locale, tgt_locale, segments):
    """
    Ingests translated segments into a translated instance.

    Args:
        original_obj (Model): The original instance that the segments were extracted from.
        translated_obj (Model): The translated instance that we are ingesting segments into.
        src_local (Locale): The locale of the source instance.
        tgt_locale (Locale): The locale of the translated instance
        segments (list[StringSegmentValue, TemplateSegmentValue, RelatedObjectSegmentValue, or OverridableSegmentValue]):
            The segment values to ingest
    """
    # Get segments by field name
    segments_by_field_name = defaultdict(list)
    for segment in segments:
        field_name, segment = segment.unwrap()
        segments_by_field_name[field_name].append(segment)

    for field_name, field_segments in segments_by_field_name.items():
        field = translated_obj.__class__._meta.get_field(field_name)

        if hasattr(field, "restore_translated_segments"):
            value = field.value_from_object(original_obj)
            new_value = field.restore_translated_segments(value, field_segments)
            setattr(translated_obj, field_name, new_value)

        elif isinstance(field, StreamField):
            data = field.value_from_object(original_obj)
            StreamFieldSegmentsWriter(
                field, src_locale, tgt_locale
            ).handle_stream_block(data, field_segments)
            setattr(translated_obj, field_name, data)

        elif isinstance(field, RichTextField):
            format, template, strings = organise_template_segments(field_segments)
            assert format == "html"
            html = restore_strings(template, strings)
            setattr(translated_obj, field_name, html)

        elif isinstance(field, (models.TextField, models.CharField)):
            if len(field_segments) > 1:
                raise ValueError(
                    "TextField/CharField can only have a single segment. Found {}".format(
                        len(field_segments)
                    )
                )

            segment = field_segments[0]

            if isinstance(segment, OverridableSegmentValue):
                setattr(translated_obj, field_name, segment.data)
            else:
                # Assume it's a StringSegmentValue
                setattr(translated_obj, field_name, segment.render_text())

        elif isinstance(field, models.ForeignKey):
            related_translated = handle_related_object(
                field.related_model, src_locale, tgt_locale, field_segments
            )
            setattr(translated_obj, field_name, related_translated)

        elif isinstance(field, (models.ManyToOneRel)):
            original_manager = getattr(original_obj, field_name)
            translated_manager = getattr(translated_obj, field_name)

            segments_by_child = defaultdict(list)

            for segment in field_segments:
                child_translation_key, segment = segment.unwrap()
                segments_by_child[child_translation_key].append(segment)

            for child_translation_key, child_segments in segments_by_child.items():
                # The child objects must be synchronised before calling this function, so we
                # can assume that both exist
                original_child_object = original_manager.get(
                    translation_key=child_translation_key
                )
                translated_child_object = translated_manager.get(
                    translation_key=child_translation_key
                )

                ingest_segments(
                    original_child_object,
                    translated_child_object,
                    src_locale,
                    tgt_locale,
                    child_segments,
                )
