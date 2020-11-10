from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import TranslatableMixin

from wagtail_localize.segments import (
    StringSegmentValue,
    TemplateSegmentValue,
    RelatedObjectSegmentValue,
    OverridableSegmentValue,
)

from ..fields import get_translatable_fields
from ..strings import extract_strings


class StreamFieldSegmentExtractor:
    def __init__(self, field, include_overridables=False):
        self.field = field
        self.include_overridables = include_overridables

    def handle_block(self, block_type, block_value):
        if hasattr(block_type, "get_translatable_segments"):
            return block_type.get_translatable_segments(block_value)

        elif isinstance(block_type, (blocks.URLBlock, blocks.EmailBlock)):
            if self.include_overridables:
                return [OverridableSegmentValue("", block_value)]
            else:
                return []

        elif isinstance(block_type, (blocks.CharBlock, blocks.TextBlock, blocks.BlockQuoteBlock)):
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

        # Ignore everything else
        return []

    def handle_related_object_block(self, related_object):
        if related_object is None:
            return []

        if isinstance(related_object, TranslatableMixin):
            return [RelatedObjectSegmentValue.from_instance("", related_object)]
        else:
            return [OverridableSegmentValue("", related_object.pk)]

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

    for translatable_field in get_translatable_fields(instance.__class__):
        field = translatable_field.get_field(instance.__class__)
        is_translatable = translatable_field.is_translated(instance)
        is_synchronized = translatable_field.is_synchronized(instance)

        if hasattr(field, "get_translatable_segments"):
            if is_translatable:
                segments.extend(
                    segment.wrap(field.name)
                    for segment in field.get_translatable_segments(
                        field.value_from_object(instance)
                    )
                )

        elif isinstance(field, StreamField):
            if is_translatable:
                segments.extend(
                    segment.wrap(field.name)
                    for segment in StreamFieldSegmentExtractor(field, include_overridables=is_synchronized).handle_stream_block(
                        field.value_from_object(instance)
                    )
                )

        elif isinstance(field, RichTextField):
            if is_translatable:
                template, strings = extract_strings(field.value_from_object(instance))

                field_segments = [TemplateSegmentValue("", "html", template, len(strings))] + [
                    StringSegmentValue("", string, attrs=attrs) for string, attrs in strings
                ]

                segments.extend(segment.wrap(field.name) for segment in field_segments)

            if is_synchronized:
                pass  # TODO: Extract images and links

        elif isinstance(field, (models.TextField, models.CharField)):
            if not field.choices:
                value = field.value_from_object(instance)

                if value is None:
                    continue

                if is_translatable:
                    segments.append(
                        StringSegmentValue(field.name, value)
                    )

                elif is_synchronized:
                    segments.append(
                        OverridableSegmentValue(field.name, value)
                    )

        elif isinstance(field, (models.ForeignKey)):
            if is_translatable:
                if not issubclass(field.related_model, TranslatableMixin):
                    # TODO: ImproperlyConfiguredError
                    raise Exception

                related_instance = getattr(instance, field.name)

                if related_instance:
                    segments.append(
                        RelatedObjectSegmentValue.from_instance(field.name, related_instance)
                    )

            elif is_synchronized:
                related_instance = getattr(instance, field.name)

                if related_instance:
                    segments.append(
                        OverridableSegmentValue(field.name, related_instance.pk)
                    )
        elif (
            isinstance(field, (models.ManyToOneRel))
            and isinstance(field.remote_field, ParentalKey)
            and issubclass(field.related_model, TranslatableMixin)
        ):
            manager = getattr(instance, field.name)

            if is_translatable:
                for child_instance in manager.all():
                    segments.extend(
                        segment.wrap(str(child_instance.translation_key)).wrap(field.name)
                        for segment in extract_segments(child_instance)
                    )

            elif is_synchronized:
                pass  # TODO

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
