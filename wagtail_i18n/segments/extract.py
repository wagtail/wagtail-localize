from django.db import models

from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.rich_text import RichText
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from wagtail_i18n.models import TranslatableMixin
from wagtail_i18n.segments import SegmentValue


class StreamFieldSegmentExtractor:
    def __init__(self, field):
        self.field = field

    def handle_block(self, block_type, block_value):
        if hasattr(block_type, 'get_translatable_segments'):
            return block_type.get_translatable_segments(block_value)

        elif isinstance(block_type, (blocks.CharBlock, blocks.TextBlock)):
            return [SegmentValue('', block_value)]

        elif isinstance(block_type, blocks.RichTextBlock):
            return [SegmentValue('', block_value.source, format='html')]

        elif isinstance(block_type, (ImageChooserBlock, SnippetChooserBlock)):
            return self.handle_related_object_block(block_value)

        elif isinstance(block_type, blocks.StructBlock):
            return self.handle_struct_block(block_value)

        elif isinstance(block_type, blocks.ListBlock):
            return self.handle_list_block(block_value)

        elif isinstance(block_type, blocks.ChoiceBlock):
            return []

        else:
            raise Exception("Unrecognised StreamField block type '{}'. Have you implemented get_translatable_segments on this class?".format(block_type.__class__.__name__))

    def handle_related_object_block(self, related_object):
        if related_object is None or not isinstance(related_object, TranslatableMixin):
            return []

        return extract_segments(related_object)

    def handle_struct_block(self, struct_block):
        segments = []

        for field_name, block_value in struct_block.items():
            block_type = struct_block.block.child_blocks[field_name]
            segments.extend(segment.wrap(field_name) for segment in self.handle_block(block_type, block_value))

        return segments

    def handle_list_block(self, list_block):
        # TODO
        return []

    def handle_stream_block(self, stream_block):
        segments = []

        for block in stream_block:
            segments.extend(segment.wrap(block.id) for segment in self.handle_block(block.block, block.value))

        return segments


def extract_segments(instance):
    segments = []

    for field in instance.get_translatable_fields():
        if isinstance(field, StreamField):
            segments.extend(segment.wrap(field.name) for segment in StreamFieldSegmentExtractor(field).handle_stream_block(field.value_from_object(instance)))

        elif isinstance(field, RichTextField):
            segments.append(SegmentValue(field.name, field.value_from_object(instance), format='html'))

        elif isinstance(field, (models.TextField, models.CharField)):
            if not field.choices:
                segments.append(SegmentValue(field.name, field.value_from_object(instance)))

        elif isinstance(field, (models.ForeignKey)) and issubclass(field.related_model, TranslatableMixin):
            related_instance = getattr(instance, field.name)

            if related_instance:
                segments.extend(segment.wrap(field.name) for segment in extract_segments(related_instance))

        elif isinstance(field, (models.ManyToOneRel)) and issubclass(field.related_model, TranslatableMixin):
            manager = getattr(instance, field.name)

            for child_instance in manager.all():
                segments.extend(segment.wrap(f'{field.name}.{child_instance.translation_key}') for segment in extract_segments(child_instance))

    return [segment for segment in segments if segment.text not in [None, '']]
