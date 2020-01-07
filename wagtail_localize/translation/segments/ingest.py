from collections import defaultdict

from django.db import models

from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.rich_text import RichText
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from wagtail_localize.models import TranslatableMixin
from wagtail_localize.translation.segments import TemplateValue

from .html import restore_html_segments


def organise_template_segments(segments):
    # The first segment is always the template, followed by the texts in order of their position
    segments.sort(key=lambda segment: segment.order)
    template = segments[0]
    return (
        template.format,
        template.template,
        [segment.html for segment in segments[1:]],
    )


def handle_related_object(related_object, src_locale, tgt_locale, segments):
    # FIXME: Check that segments is a single item list
    related_object_value = segments[0]
    return related_object_value.get_instance(tgt_locale)


class StreamFieldSegmentsWriter:
    def __init__(self, field, src_locale, tgt_locale):
        self.field = field
        self.src_locale = src_locale
        self.tgt_locale = tgt_locale

    def handle_block(self, block_type, block_value, segments):
        if hasattr(block_type, "restore_translated_segments"):
            return block_type.restore_translated_segments(block_value, segments)

        elif isinstance(block_type, (blocks.CharBlock, blocks.TextBlock)):
            return segments[0].text

        elif isinstance(block_type, blocks.RichTextBlock):
            format, template, segments = organise_template_segments(segments)
            assert format == "html"
            return RichText(restore_html_segments(template, segments))

        elif isinstance(block_type, (ImageChooserBlock, SnippetChooserBlock)):
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
            related_object, self.src_locale, self.tgt_locale, segments
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
        # TODO
        pass

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
            format, template, segments = organise_template_segments(field_segments)
            assert format == "html"
            html = restore_html_segments(template, segments)
            setattr(translated_obj, field_name, html)

        elif isinstance(field, (models.TextField, models.CharField)):
            setattr(translated_obj, field_name, field_segments[0].text)

        elif isinstance(field, models.ForeignKey):
            related_original = getattr(original_obj, field_name)
            related_translated = handle_related_object(
                related_original, src_locale, tgt_locale, field_segments
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
                original_child_object = original_manager.filter(
                    translation_key=child_translation_key
                ).first()
                translated_child_object = translated_manager.filter(
                    translation_key=child_translation_key
                ).first()

                if not translated_child_object:
                    # TODO: Here, we expect that the inline child to already exist as Wagtail copies it
                    # when creating the translated page. When we add editing, we will need to support
                    # adding new inline objects manually.
                    continue

                ingest_segments(
                    original_child_object,
                    translated_child_object,
                    src_locale,
                    tgt_locale,
                    child_segments,
                )
                translated_child_object.save()
