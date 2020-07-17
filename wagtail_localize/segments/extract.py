from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import TranslatableMixin
from wagtail.embeds.blocks import EmbedBlock

from wagtail_localize.segments import (
    StringSegmentValue,
    TemplateSegmentValue,
    RelatedObjectSegmentValue,
)

from ..strings import extract_strings


class StreamFieldSegmentExtractor:
    def __init__(self, field):
        self.field = field

    def handle_block(self, block_type, block_value):
        if hasattr(block_type, "get_translatable_segments"):
            return block_type.get_translatable_segments(block_value)

        elif isinstance(block_type, (blocks.CharBlock, blocks.TextBlock)):
            return [StringSegmentValue("", block_value)]

        elif isinstance(block_type, blocks.RichTextBlock):
            template, strings = extract_strings(block_value.source)

            return [TemplateSegmentValue("", "html", template, len(strings))] + [
                StringSegmentValue("", string, attrs=attrs) for string, attrs in strings
            ]

        elif isinstance(block_type, blocks.ChooserBlock):
            return self.handle_related_object_block(block_value)

        elif isinstance(block_type, blocks.StructBlock):
            return self.handle_struct_block(block_value)

        elif isinstance(block_type, blocks.ListBlock):
            return self.handle_list_block(block_value)

        elif isinstance(block_type, blocks.StreamBlock):
            return self.handle_stream_block(block_value)

        elif isinstance(block_type, (blocks.ChoiceBlock, EmbedBlock)):
            return []

        else:
            raise Exception(
                "Unrecognised StreamField block type '{}'. Have you implemented get_translatable_segments on this class?".format(
                    block_type.__class__.__name__
                )
            )

    def handle_related_object_block(self, related_object):
        if related_object is None or not isinstance(related_object, TranslatableMixin):
            return []

        return RelatedObjectSegmentValue.from_instance("", related_object)

    def handle_struct_block(self, struct_block):
        segments = []

        for field_name, block_value in struct_block.items():
            block_type = struct_block.block.child_blocks[field_name]
            segments.extend(
                segment.wrap(field_name)
                for segment in self.handle_block(block_type, block_value)
            )

        return segments

    def handle_list_block(self, list_block):
        # TODO
        return []

    def handle_stream_block(self, stream_block):
        segments = []

        for block in stream_block:
            segments.extend(
                segment.wrap(block.id)
                for segment in self.handle_block(block.block, block.value)
            )

        return segments


def extract_segments(instance):
    segments = []

    for translatable_field in getattr(instance, 'translatable_fields', []):
        if not translatable_field.is_translated(instance):
            continue

        field = translatable_field.get_field(instance.__class__)

        if hasattr(field, "get_translatable_segments"):
            segments.extend(
                segment.wrap(field.name)
                for segment in field.get_translatable_segments(
                    field.value_from_object(instance)
                )
            )

        elif isinstance(field, StreamField):
            segments.extend(
                segment.wrap(field.name)
                for segment in StreamFieldSegmentExtractor(field).handle_stream_block(
                    field.value_from_object(instance)
                )
            )

        elif isinstance(field, RichTextField):
            template, strings = extract_strings(field.value_from_object(instance))

            field_segments = [TemplateSegmentValue("", "html", template, len(strings))] + [
                StringSegmentValue("", string, attrs=attrs) for string, attrs in strings
            ]

            segments.extend(segment.wrap(field.name) for segment in field_segments)

        elif isinstance(field, (models.TextField, models.CharField)):
            if not field.choices:
                segments.append(
                    StringSegmentValue(field.name, field.value_from_object(instance))
                )

        elif isinstance(field, (models.ForeignKey)) and issubclass(
            field.related_model, TranslatableMixin
        ):
            related_instance = getattr(instance, field.name)

            if related_instance:
                segments.append(
                    RelatedObjectSegmentValue.from_instance(field.name, related_instance)
                )

        elif (
            isinstance(field, (models.ManyToOneRel))
            and isinstance(field.remote_field, ParentalKey)
            and issubclass(field.related_model, TranslatableMixin)
        ):
            manager = getattr(instance, field.name)

            for child_instance in manager.all():
                segments.extend(
                    segment.wrap(str(child_instance.translation_key)).wrap(field.name)
                    for segment in extract_segments(child_instance)
                )

    class Counter:
        def __init__(self):
            self.value = 0

        def next(self):
            self.value += 1
            return self.value

    counter = Counter()

    return [
        segment.with_order(counter.next())
        for segment in segments
        if not segment.is_empty()
    ]
