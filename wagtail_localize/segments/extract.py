from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page, TranslatableMixin

from wagtail_localize.segments import (
    OverridableSegmentValue,
    RelatedObjectSegmentValue,
    StringSegmentValue,
    TemplateSegmentValue,
)

from ..fields import get_translatable_fields
from ..strings import extract_strings


def quote_path_component(text):
    """
    Puts quotes around the path compoenents, and escapes any special characters.
    """
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


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

    def handle_block(self, block_type, block_value, raw_value=None):
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

        elif isinstance(
            block_type, (blocks.CharBlock, blocks.TextBlock, blocks.BlockQuoteBlock)
        ):
            return [StringSegmentValue("", block_value)]

        elif isinstance(block_type, blocks.RichTextBlock):
            template, strings = extract_strings(block_value.source)

            # Find all unique href values
            hrefs = set()
            for _string, attrs in strings:
                for tag_attrs in attrs.values():
                    if "href" in tag_attrs:
                        hrefs.add(tag_attrs["href"])

            ret = (
                [TemplateSegmentValue("", "html", template, len(strings))]
                + [
                    StringSegmentValue("", string, attrs=attrs)
                    for string, attrs in strings
                ]
                + [
                    OverridableSegmentValue(quote_path_component(href), href)
                    for href in sorted(hrefs)
                ]
            )
            return ret

        elif isinstance(block_type, blocks.ChooserBlock):
            return self.handle_related_object_block(block_value)

        elif isinstance(block_type, blocks.StructBlock):
            return self.handle_struct_block(block_value, raw_value=raw_value)

        elif isinstance(block_type, blocks.ListBlock):
            return self.handle_list_block(block_value, raw_value=raw_value)

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
        if isinstance(related_object, TranslatableMixin) and not isinstance(
            related_object, Page
        ):
            return [RelatedObjectSegmentValue.from_instance("", related_object)]
        else:
            return [OverridableSegmentValue("", related_object.pk)]

    def handle_struct_block(self, struct_block, raw_value=None):
        segments = []

        for field_name, block_value in struct_block.items():
            block_type = struct_block.block.child_blocks[field_name]
            try:
                block_raw_value = raw_value["value"].get(field_name)
            except (KeyError, TypeError):
                # e.g. raw_value is None, or is that from chooser
                block_raw_value = None
            segments.extend(
                segment.wrap(field_name)
                for segment in self.handle_block(
                    block_type, block_value, raw_value=block_raw_value
                )
            )

        return segments

    def handle_list_block(self, list_block, raw_value=None):
        segments = []
        if WAGTAIL_VERSION >= (2, 16) and raw_value is not None:
            # Wagtail 2.16 changes ListBlock values to be ListValue objects (i.e. {'value': '', 'id': ''})
            # and will automatically convert from the simple list format used before. However that requires
            # the block to be saved. bound_blocks will return ListValue objects, so we need to check that the
            # stored value is the new format before extracting segments, otherwise the block ids will continue
            # to change.
            has_block_format = False
            if (
                isinstance(raw_value, dict)
                and "value" in raw_value
                and len(raw_value["value"]) > 0
            ):
                has_block_format = list_block.list_block._item_is_in_block_format(
                    raw_value["value"][0]
                )
            elif isinstance(raw_value, list) and len(raw_value) > 0:
                has_block_format = list_block.list_block._item_is_in_block_format(
                    raw_value[0]
                )
            if has_block_format:
                for index, block in enumerate(list_block.bound_blocks):
                    # pass on the relevant sub-block raw value, should it be a ListBlock
                    try:
                        if isinstance(raw_value, list):
                            block_raw_value = raw_value[index]
                        elif isinstance(raw_value, dict):
                            block_raw_value = raw_value["value"][index]
                        else:
                            block_raw_value = None
                    except (IndexError, KeyError):
                        block_raw_value = None

                    segments.extend(
                        segment.wrap(block.id)
                        for segment in self.handle_block(
                            block.block, block.value, raw_value=block_raw_value
                        )
                    )
        return segments

    def handle_stream_block(self, stream_block):
        segments = []

        for index, block in enumerate(stream_block):
            raw_data = (
                stream_block.raw_data[index] if WAGTAIL_VERSION >= (2, 16) else None
            )
            segments.extend(
                segment.wrap(block.id)
                for segment in self.handle_block(
                    block.block, block.value, raw_value=raw_data
                )
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
        is_overridable = translatable_field.is_overridable(instance)
        extract_overridables = is_synchronized and is_overridable

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
                    for segment in StreamFieldSegmentExtractor(
                        field, include_overridables=extract_overridables
                    ).handle_stream_block(field.value_from_object(instance))
                )

        elif isinstance(field, RichTextField):
            value = field.value_from_object(instance)

            if is_translatable:
                template, strings = extract_strings(value)

                # Find all unique href values
                hrefs = set()
                for _string, attrs in strings:
                    for tag_attrs in attrs.values():
                        if "href" in tag_attrs:
                            hrefs.add(tag_attrs["href"])

                field_segments = (
                    [TemplateSegmentValue("", "html", template, len(strings))]
                    + [
                        StringSegmentValue("", string, attrs=attrs)
                        for string, attrs in strings
                    ]
                    + [
                        OverridableSegmentValue(quote_path_component(href), href)
                        for href in sorted(hrefs)
                    ]
                )

                segments.extend(segment.wrap(field.name) for segment in field_segments)

            if extract_overridables:
                pass  # TODO: Extract images and links

        elif isinstance(field, (models.TextField, models.CharField)):
            if not field.choices:
                value = field.value_from_object(instance)

                if value is None:
                    continue

                if is_translatable:
                    segments.append(StringSegmentValue(field.name, value))

                elif extract_overridables:
                    segments.append(OverridableSegmentValue(field.name, value))

        elif isinstance(field, models.ForeignKey):
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
                        RelatedObjectSegmentValue.from_instance(
                            field.name, related_instance
                        )
                    )

            elif extract_overridables:
                related_instance = getattr(instance, field.name)

                if related_instance:
                    segments.append(
                        OverridableSegmentValue(field.name, related_instance.pk)
                    )
        elif (
            isinstance(field, models.ManyToOneRel)
            and isinstance(field.remote_field, ParentalKey)
            and issubclass(field.related_model, TranslatableMixin)
        ):
            manager = getattr(instance, field.name)

            if is_translatable:
                for child_instance in manager.all():
                    segments.extend(
                        segment.wrap(str(child_instance.translation_key)).wrap(
                            field.name
                        )
                        for segment in extract_segments(child_instance)
                    )

            elif extract_overridables:
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
