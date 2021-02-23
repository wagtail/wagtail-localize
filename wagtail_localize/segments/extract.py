from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import TranslatableMixin, Page

from wagtail_localize.segments import (
    StringSegmentValue,
    TemplateSegmentValue,
    RelatedObjectSegmentValue,
    OverridableSegmentValue,
)

from ..fields import get_translatable_fields
from ..strings import extract_strings


def quote_path_component(text):
    """
    Puts quotes around the path compoenents, and escapes any special characters.
    """
    return "'" + text.replace("\\", "\\\\") .replace("'", "\\'") + "'"


class StreamFieldSegmentExtractor:
    """
    A helper class to help traverse StreamField values and extract segments.
    """
    def __init__(self, field, include_overridables=False):
        """
        Initialises a StreamFieldSegmentExtractor.

        Args:
            field (StreamField): The StreamField to extract segments from.
            include_overridables (boolean, optional): Set this to True to extract overridable segments too.
        """
        self.field = field
        self.include_overridables = include_overridables

    def handle_block(self, block_type, block_value):
        # Need to check if the app is installed before importing EmbedBlock
        # See: https://github.com/wagtail/wagtail-localize/issues/309
        if apps.is_installed("wagtail.embeds"):
            from wagtail.embeds.blocks import EmbedBlock

            if isinstance(block_type, EmbedBlock):
                if self.include_overridables:
                    return [OverridableSegmentValue("", block_value.url)]
                else:
                    return []

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

            # Find all unique href values
            hrefs = set()
            for string, attrs in strings:
                for tag_attrs in attrs.values():
                    if 'href' in tag_attrs:
                        hrefs.add(tag_attrs['href'])

            ret = [
                TemplateSegmentValue("", "html", template, len(strings))
            ] + [
                StringSegmentValue("", string, attrs=attrs)
                for string, attrs in strings
            ] + [
                OverridableSegmentValue(quote_path_component(href), href)
                for href in sorted(hrefs)
            ]
            return ret

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

        # All FKs to translatable models should be translatable.
        # With the exception of pages that are special because we can localize them at runtime easily.
        # TODO: Perhaps we need a special type for pages where it links to the translation if availabe,
        # but falls back to the source if it isn't translated yet?
        # Note: This exact same decision was made for regular foreign keys in fields.py
        if isinstance(related_object, TranslatableMixin) and not isinstance(related_object, Page):
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
    """
    Extracts segments from the given model instance.

    Args:
        instance (Model): The model instance to extract segments from.

    Returns:
        list[StringSegmentValue, TemplateSegmentValue, RelatedObjectSegmentValue, or OverridableSegmentValue]: The
            segment values that have been extracted.
    """
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

                # Find all unique href values
                hrefs = set()
                for string, attrs in strings:
                    for tag_attrs in attrs.values():
                        if 'href' in tag_attrs:
                            hrefs.add(tag_attrs['href'])

                field_segments = [
                    TemplateSegmentValue("", "html", template, len(strings))
                ] + [
                    StringSegmentValue("", string, attrs=attrs)
                    for string, attrs in strings
                ] + [
                    OverridableSegmentValue(quote_path_component(href), href)
                    for href in sorted(hrefs)
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
                    raise ImproperlyConfigured(
                        "The foreign key `{}.{}.{}` was registered as a translatable "
                        "field but the model it points to `{}.{}` is not translatable".format(
                            field.model._meta.app_label,
                            field.model.__name__,
                            field.name,
                            field.related_model._meta.app_label,
                            field.related_model.__name__,
                        )
                    )

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
