from django.contrib.contenttypes.models import ContentType

from wagtail_localize.strings import StringValue


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

        >>> s = StringSegmentValue('field', 'foo')
        >>> s.wrap('wrapped')
        StringSegmentValue('wrapped.field', 'foo')
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

        >>> s = StringSegmentValue('wrapped.field', 'foo')
        >>> s.unwrap()
        'wrapped', StringSegmentValue('field', 'foo')
        """
        first_component, *remaining_components = self.path.split(".")
        new_path = ".".join(remaining_components)

        clone = self.clone()
        clone.path = new_path
        return first_component, clone


class StringSegmentValue(BaseValue):
    def __init__(self, path, string, attrs=None, **kwargs):
        if isinstance(string, str):
            string = StringValue.from_plaintext(string)

        self.string = string
        self.attrs = attrs or None

        super().__init__(path, **kwargs)

    def clone(self):
        return StringSegmentValue(
            self.path, self.string, attrs=self.attrs, order=self.order
        )

    @classmethod
    def from_source_html(cls, path, html, **kwargs):
        string, attrs = StringValue.from_source_html(html)
        return cls(path, string, attrs=attrs, **kwargs)

    def render_text(self):
        return self.string.render_text()

    def render_html(self):
        return self.string.render_html(self.attrs)

    def is_empty(self):
        return self.string.data in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, StringSegmentValue)
            and self.path == other.path
            and self.string == other.string
            and self.attrs == other.attrs
        )

    def __repr__(self):
        return "<StringSegmentValue {} '{}'>".format(self.path, self.render_html())


class TemplateSegmentValue(BaseValue):
    def __init__(self, path, format, template, string_count, **kwargs):
        self.format = format
        self.template = template
        self.string_count = string_count

        super().__init__(path, **kwargs)

    def clone(self):
        return TemplateSegmentValue(
            self.path, self.format, self.template, self.string_count, order=self.order
        )

    def is_empty(self):
        return self.template in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, TemplateSegmentValue)
            and self.path == other.path
            and self.format == other.format
            and self.template == other.template
            and self.string_count == other.string_count
        )

    def __repr__(self):
        return "<TemplateSegmentValue {} format:{} {} segments>".format(
            self.path, self.format, self.string_count
        )


class RelatedObjectSegmentValue(BaseValue):
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
        return RelatedObjectSegmentValue(
            self.path, self.content_type, self.translation_key, order=self.order
        )

    def is_empty(self):
        return self.content_type is None and self.translation_key is None

    def __eq__(self, other):
        return (
            isinstance(other, RelatedObjectSegmentValue)
            and self.path == other.path
            and self.content_type == other.content_type
            and self.translation_key == other.translation_key
        )

    def __repr__(self):
        return "<RelatedObjectSegmentValue {} {} {}>".format(
            self.path, self.content_type, self.translation_key
        )


class OverridableSegmentValue(BaseValue):
    def __init__(self, path, data, **kwargs):
        self.data = data

        super().__init__(path, **kwargs)

    def clone(self):
        return OverridableSegmentValue(
            self.path, self.data, order=self.order
        )

    def is_empty(self):
        return self.data in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, OverridableSegmentValue)
            and self.path == other.path
            and self.data == other.data
        )

    def __repr__(self):
        return "<OverridableSegmentValue {} '{}'>".format(self.path, self.data)
