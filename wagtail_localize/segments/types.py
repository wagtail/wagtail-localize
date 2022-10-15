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
    """
    Represents a translatable string segment.

    Attributes:
        path (str): The content path of the segment.
        string (StringValue): the value of the segment.
        attrs (dict): A dict of HTML attributes that were stripped out of the string.
        order (int): The index that this segment appears on a page.
    """

    def __init__(self, path, string, attrs=None, **kwargs):
        """
        Initialises a new StringSegmentValue.

        Args:
            path (str): The content path of the segment.
            string (StringValue): the value of the segment.
            attrs (dict, optional): A dict of HTML attributes that were stripped out of the string.
            order (int, optional): The index that this segment appears on a page.
        """
        if isinstance(string, str):
            string = StringValue.from_plaintext(string)

        elif isinstance(string, StringValue):
            pass

        else:
            raise TypeError(
                "`string` must be either a `StringValue` or a `str`. Got `{}`".format(
                    type(string).__name__
                )
            )

        self.string = string
        self.attrs = attrs or None

        super().__init__(path, **kwargs)

    def clone(self):
        """
        Makes an exact copy of this StringSegmentValue.

        Instead of mutating SegmentValue classes in place, it's recommended to clone them first.

        Returns:
            StringSegmentValue: The new segment value that's a copy of this one.
        """
        return StringSegmentValue(
            self.path, self.string, attrs=self.attrs, order=self.order
        )

    @classmethod
    def from_source_html(cls, path, html, **kwargs):
        """
        Initialises a StringSegmentValue from a HTML string.

        Args:
            path (str): The content path of the segment.
            html (str): The HTML value of the segment.
            order (int, optional): The index that this segment appears on a page.
        """
        string, attrs = StringValue.from_source_html(html)
        return cls(path, string, attrs=attrs, **kwargs)

    def render_text(self):
        """
        Returns a plain text representation of the segment value.

        Note: If the segment value was created from HTML, this strips out HTML tags.

        Returns:
            str: The text representation of the segment value.
        """
        return self.string.render_text()

    def render_html(self):
        """
        Returns a HTML representation of the segment value.

        Note: If the segment value was created from plain text, this escapes special characters.

        Returns:
            str: The HTML representation of the segment value.
        """
        return self.string.render_html(self.attrs)

    def is_empty(self):
        """
        Returns True if the StringValue is blank.

        Returns:
            boolean: True if the StringValue is blank.
        """
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
    """
    Represents an HTML template used to recombine the values of RichTextField/Blocks.

    Attributes:
        path (str): The content path of the segment.
        format (str): The format of the template (eg, 'html').
        template (str): The template.
        string_count (int): The number of translatablle string segments that were extracted from the template.
        order (int): The index that this segment appears on a page.
    """

    def __init__(self, path, format, template, string_count, **kwargs):
        """
        Initialises a new TemplateSegmentValue.

        Args:
            path (str): The content path of the segment.
            format (str): The format of the template (eg, 'html').
            template (str): The template.
            string_count (int): The number of translatablle string segments that were extracted from the template.
            order (int, optional): The index that this segment appears on a page.
        """
        self.format = format
        self.template = template
        self.string_count = string_count

        super().__init__(path, **kwargs)

    def clone(self):
        """
        Makes an exact copy of this TemplateSegmentValue.

        Instead of mutating SegmentValue classes in place, it's recommended to clone them first.

        Returns:
            TemplateSegmentValue: The new segment value that's a copy of this one.
        """
        return TemplateSegmentValue(
            self.path, self.format, self.template, self.string_count, order=self.order
        )

    def is_empty(self):
        """
        Returns True if the template is blank.

        Returns:
            boolean: True if the template is blank.
        """
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
    """
    Represents a reference to a foreign translatable object.

    Attributes:
        path (str): The content path of the segment.
        content_type (ContentType): The content type of the base model of the foreign object.
        translation_key (UUID): The value of the foreign object's `translation_key` field.
        order (int): The index that this segment appears on a page.
    """

    def __init__(self, path, content_type, translation_key, **kwargs):
        """
        Initialises a new RelatedObjectSegmentValue.

        Args:
            path (str): The content path of the segment.
            content_type (ContentType): The content type of the base model of the foreign object.
            translation_key (UUID): The value of the foreign object's `translation_key` field.
            order (int, optional): The index that this segment appears on a page.
        """
        self.content_type = content_type
        self.translation_key = translation_key

        super().__init__(path, **kwargs)

    @classmethod
    def from_instance(cls, path, instance):
        """
        Initialises a new RelatedObjectSegmentValue from a model instance.

        Note: This class only records the type and translation key of the instance. So you will need to save the
        locale separately if you need to get this same instance back later.

        Args:
            path (str): The content path of the segment.
            instance (Model): An instance of the translatable object that needs to be referenced.

        Raises:
            AttributeError: If the instance is not translatable.

        Returns:
            RelatedObjectSegmentValue: The new segment value.
        """
        model = instance.get_translation_model()
        return cls(
            path, ContentType.objects.get_for_model(model), instance.translation_key
        )

    def get_instance(self, locale):
        """
        Gets an instance of the referenced translatable object for the given locale.

        Raises:
            Model.DoesNotExist: If there isn't an instance of the translatable object in the given locale.

        Returns:
            Model: The instance.
        """
        from ..models import pk

        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale_id=pk(locale)
        )

    def clone(self):
        """
        Makes an exact copy of this RelatedObjectSegmentValue.

        Instead of mutating SegmentValue classes in place, it's recommended to clone them first.

        Returns:
            RelatedObjectSegmentValue: The new segment value that's a copy of this one.
        """
        return RelatedObjectSegmentValue(
            self.path, self.content_type, self.translation_key, order=self.order
        )

    def is_empty(self):
        """
        Returns True if the related object is null.

        Returns:
            boolean: True if the related object is null.
        """
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
    """
    Represents a field that can be overridden.

    Attributes:
        path (str): The content path of the segment.
        data (any): The value of the field in the source. Must be JSON-serializable.
        order (int): The index that this segment appears on a page.
    """

    def __init__(self, path, data, **kwargs):
        """
        Initialises a new RelatedObjectSegmentValue.

        Args:
            path (str): The content path of the segment.
            data (any): The value of the field in the source. Must be JSON-serializable.
            order (int, optional): The index that this segment appears on a page.
        """
        self.data = data

        super().__init__(path, **kwargs)

    def clone(self):
        """
        Makes an exact copy of this OverridableSegmentValue.

        Instead of mutating SegmentValue classes in place, it's recommended to clone them first.

        Returns:
            OverridableSegmentValue: The new segment value that's a copy of this one.
        """
        return OverridableSegmentValue(self.path, self.data, order=self.order)

    def is_empty(self):
        """
        Returns True if the data is empty.

        Returns:
            boolean: True if the data is empty.
        """
        return self.data in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, OverridableSegmentValue)
            and self.path == other.path
            and self.data == other.data
        )

    def __repr__(self):
        return "<OverridableSegmentValue {} '{}'>".format(self.path, self.data)
