from django.db import models

from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.rich_text import RichText
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from wagtail_i18n.models import TranslatableMixin


class Segment:
    def __init__(self, path, text, html=False):
        self.path = path
        self.text = text
        self.html = html

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = Segment('field', "The text")
        >>> s.wrap('relation')
        Segment('relation.field', "The text")
        """
        new_path = base_path

        if self.path:
            new_path += '.' + self.path

        return Segment(new_path, self.text, html=self.html)

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = Segment('relation.field', "The text")
        >>> s.unwrap()
        'relation', Segment('field', "The text")
        """
        base_path, *remaining_components = self.path.split('.')
        new_path = '.'.join(remaining_components)
        return base_path, Segment(new_path, self.text, html=self.html)

    def __eq__(self, other):
        return isinstance(other, Segment) and self.path == other.path and self.text == other.text

    def __repr__(self):
        return f'<Segment {self.path} "{self.text}">'


class StreamFieldSegmentizer:
    def __init__(self, field):
        self.field = field

    def handle_block(self, block_type, block_value):
        if hasattr(block_type, 'get_translatable_segments'):
            return block_type.get_translatable_segments(block_value)

        elif isinstance(block_type, (blocks.CharBlock, blocks.TextBlock)):
            return [Segment('', block_value)]

        elif isinstance(block_type, blocks.RichTextBlock):
            return [Segment('', block_value.source, html=True)]

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

        return segmentize(related_object)

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


def segmentize(instance):
    segments = []

    for field in instance.get_translatable_fields():
        if isinstance(field, StreamField):
            segments.extend(segment.wrap(field.name) for segment in StreamFieldSegmentizer(field).handle_stream_block(field.value_from_object(instance)))

        elif isinstance(field, RichTextField):
            segments.append(Segment(field.name, field.value_from_object(instance), html=True))

        elif isinstance(field, (models.TextField, models.CharField)):
            if not field.choices:
                segments.append(Segment(field.name, field.value_from_object(instance)))

        elif isinstance(field, (models.ForeignKey)) and issubclass(field.related_model, TranslatableMixin):
            related_instance = getattr(instance, field.name)

            if related_instance:
                segments.extend(segment.wrap(field.name) for segment in segmentize(related_instance))

        elif isinstance(field, (models.ManyToOneRel)) and issubclass(field.related_model, TranslatableMixin):
            manager = getattr(instance, field.name)

            for child_instance in manager.all():
                segments.extend(segment.wrap(f'{field.name}.{child_instance.translation_key}') for segment in segmentize(child_instance))

    return [segment for segment in segments if segment.text not in [None, '']]
