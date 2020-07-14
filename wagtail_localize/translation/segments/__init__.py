from django.contrib.contenttypes.models import ContentType

from .html import HTMLSnippet


class BaseValue:
    def __init__(self, path, order=0):
        self.path = path
        self.order = order

    def clone(self):
        """
        Clones this segment. Must be overridden in subclass.
        """
        raise NotImplementedError

    def with_order(self, order):
        """
        Sets the order of this segment.
        """
        clone = self.clone()
        clone.order = order
        return clone

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = SegmentValue('field', 'foo')
        >>> s.wrap('wrapped')
        SegmentValue('wrapped.field', 'foo')
        """
        new_path = base_path

        if self.path:
            new_path += "." + self.path

        clone = self.clone()
        clone.path = new_path
        return clone

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = SegmentValue('wrapped.field', 'foo')
        >>> s.unwrap()
        'wrapped', SegmentValue('field', 'foo')
        """
        first_component, *remaining_components = self.path.split(".")
        new_path = ".".join(remaining_components)

        clone = self.clone()
        clone.path = new_path
        return first_component, clone


class SegmentValue(BaseValue):
    def __init__(self, path, source, translation=None, **kwargs):
        if isinstance(source, str):
            source = HTMLSnippet.from_plaintext(source)

        if isinstance(translation, str):
            translation = HTMLSnippet.from_plaintext(translation)

        self.source = source
        self.translation = translation

        super().__init__(path, **kwargs)

    def clone(self):
        return SegmentValue(
            self.path, self.source, translation=self.translation, order=self.order
        )

    def is_empty(self):
        return self.source.html in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, SegmentValue)
            and self.path == other.path
            and self.source == other.source
            and self.translation == other.translation
        )

    def __repr__(self):
        if self.translation:
            return '<SegmentValue {} "{}" "{}">'.format(self.path, self.source.html, self.translation.html)
        else:
            return '<SegmentValue {} "{}">'.format(self.path, self.source.html)


class TemplateValue(BaseValue):
    def __init__(self, path, format, template, segment_count, **kwargs):
        self.format = format
        self.template = template
        self.segment_count = segment_count

        super().__init__(path, **kwargs)

    def clone(self):
        return TemplateValue(
            self.path, self.format, self.template, self.segment_count, order=self.order
        )

    def is_empty(self):
        return self.template in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, TemplateValue)
            and self.path == other.path
            and self.format == other.format
            and self.template == other.template
            and self.segment_count == other.segment_count
        )

    def __repr__(self):
        return "<TemplateValue {} format:{} {} segments>".format(
            self.path, self.format, self.segment_count
        )


class RelatedObjectValue(BaseValue):
    def __init__(self, path, content_type, translation_key, **kwargs):
        self.content_type = content_type
        self.translation_key = translation_key

        super().__init__(path, **kwargs)

    @classmethod
    def from_instance(cls, path, instance):
        model = instance.get_translation_model()
        return cls(
            path, ContentType.objects.get_for_model(model), instance.translation_key
        )

    def get_instance(self, locale):
        from ..models import pk

        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale_id=pk(locale)
        )

    def clone(self):
        return RelatedObjectValue(
            self.path, self.content_type, self.translation_key, order=self.order
        )

    def is_empty(self):
        return self.content_type is None and self.translation_key is None

    def __eq__(self, other):
        return (
            isinstance(other, RelatedObjectValue)
            and self.path == other.path
            and self.content_type == other.content_type
            and self.translation_key == other.translation_key
        )

    def __repr__(self):
        return "<RelatedObjectValue {} {} {}>".format(
            self.path, self.content_type, self.translation_key
        )
