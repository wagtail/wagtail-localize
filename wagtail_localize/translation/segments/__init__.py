from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.forms.utils import flatatt
from django.utils.html import escape

from .html import extract_html_elements, restore_html_elements


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
    class HTMLElement:
        """
        Represents the position of an inline element within an HTML segment value.

        These are used to track how inline elements such as text formatting
        and links should be moved in translated versions of a segment.

        The parameters are as follows:

        - start/end are the character offsets in the original text that this element appears
        they may be equal but end must not be less than start.
        For example, to select just the first character, the start and end offsets with be 0,1
        respectively.
        - identifier is a number that is generated from the segment extractor. It must be conserved
        by translation engines as it is used to work out where elements have moved during translation.
        """

        def __init__(self, start, end, identifier, element=None):
            self.start = start
            self.end = end
            self.identifier = identifier
            self.element = element

        @property
        def element_tag(self):
            return f"<{self.element[0]}{flatatt(self.element[1])}>"

        def __eq__(self, other):
            if not isinstance(other, SegmentValue.HTMLElement):
                return False

            return (
                self.start == other.start
                and self.end == other.end
                and self.identifier == other.identifier
                and self.element == other.element
            )

        def __repr__(self):
            return f"<SegmentValue.HTMLElement {self.identifier} '{self.element_tag}' at [{self.start}:{self.end}]>"

    def __init__(self, path, text, html_elements=None, **kwargs):
        self.text = text
        self.html_elements = html_elements

        super().__init__(path, **kwargs)

    def clone(self):
        return SegmentValue(
            self.path, self.text, html_elements=self.html_elements, order=self.order
        )

    @classmethod
    def from_html(cls, path, html):
        text, elements = extract_html_elements(html)

        html_elements = []
        counter = Counter()
        for start, end, element_type, element_attrs in elements:
            counter[element_type] += 1
            identifier = element_type + str(counter[element_type])

            html_elements.append(
                cls.HTMLElement(start, end, identifier, (element_type, element_attrs))
            )

        return cls(path, text, html_elements)

    @property
    def html(self):
        if not self.html_elements:
            return escape(self.text)

        return restore_html_elements(
            self.text,
            [(e.start, e.end, e.element[0], e.element[1]) for e in self.html_elements],
        )

    @property
    def html_with_ids(self):
        if not self.html_elements:
            return escape(self.text)

        return restore_html_elements(
            self.text,
            [
                (
                    e.start,
                    e.end,
                    e.element[0],
                    {"id": e.identifier} if e.element[1] else {},
                )
                for e in self.html_elements
            ],
        )

    def get_html_attrs(self):
        """
        Returns a mapping of html element identifiers to their attributes.

        For example, running this on the following segment:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>

        Would return the following dictionary:

            {
                "a#a1": {"href": "https://mysite.com"}
            }
        """
        return {
            f"{e.element[0]}#{e.identifier}": e.element[1]
            for e in self.html_elements or []
            if e.element[1]
        }

    def replace_html_attrs(self, attrs_map):
        """
        Replaces the attributes of the HTML elements in this segment with
        attributes in the provided mapping.

        This is used to overwrite any HTML attribute changes made to
        translated segments so they are guarenteed to not be altered by
        translators.

        For example, running this on the following segment:

            <b>Foo <a id="a1" href="https://badsite.com">Bar</a></b>

        With the following attrs_map:

            {
                "a#a1": {"href": "https://mysite.com"}
            }

        Would return the following segment:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>
        """
        for e in self.html_elements:
            key = f"{e.element[0]}#{e.identifier}"
            if key in attrs_map:
                e.element = (e.element[0], attrs_map[key])

    def is_empty(self):
        return self.html in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, SegmentValue)
            and self.path == other.path
            and self.html == other.html
        )

    def __repr__(self):
        return '<SegmentValue {} "{}">'.format(self.path, self.html)


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
        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale=locale
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
