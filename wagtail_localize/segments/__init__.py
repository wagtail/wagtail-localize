from collections import Counter

from django.forms.utils import flatatt
from django.utils.html import escape

from .html import extract_html_elements, restore_html_elements


class SegmentValue:
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

    def __init__(self, path, text, html_elements=None, order=0):
        self.path = path
        self.order = order
        self.text = text
        self.html_elements = html_elements

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

    def with_order(self, order):
        """
        Sets the order of this segment.
        """
        return SegmentValue(self.path, self.text, self.html_elements, order=order)

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = SegmentValue('field', "The text")
        >>> s.wrap('relation')
        SegmentValue('relation.field', "The text")
        """
        new_path = base_path

        if self.path:
            new_path += "." + self.path

        return SegmentValue(new_path, self.text, self.html_elements, order=self.order)

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = SegmentValue('relation.field', "The text")
        >>> s.unwrap()
        'relation', SegmentValue('field', "The text")
        """
        base_path, *remaining_components = self.path.split(".")
        new_path = ".".join(remaining_components)
        return (
            base_path,
            SegmentValue(new_path, self.text, self.html_elements, order=self.order),
        )

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

        def cat_dict(a, b):
            c = {}
            c.update(a)
            c.update(b)
            return c

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

    def get_html_element_attrs(self):
        """
        Returns a mapping of html element identifiers to their attributes.

        For example, running this on the following segment:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>

        Would return the following dictionary:

            {
                "a1": {"href": "https://mysite.com"}
            }
        """
        return {e.identifier: e.element[1] for e in self.html_elements or []}

    def replace_html_element_attrs(self, attrs_map):
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
                "a1": {"href": "https://mysite.com"}
            }

        Would return the following segment:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>
        """
        for e in html_elements:
            if e.identifier in attrs_map:
                e.element[1] = attrs_map[e.identifier]

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


class TemplateValue:
    def __init__(self, path, format, template, segment_count, order=0):
        self.path = path
        self.order = order
        self.format = format
        self.template = template
        self.segment_count = segment_count

    def with_order(self, order):
        """
        Sets the order of this segment.
        """
        return TemplateValue(
            self.path, self.format, self.template, self.segment_count, order=order
        )

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = TemplateValue('field', 'html', "<text position=\"0\">, 1)
        >>> s.wrap('relation')
        TemplateValue('relation.field', 'html', "<text position=\"0\">, 1)
        """
        new_path = base_path

        if self.path:
            new_path += "." + self.path

        return TemplateValue(
            new_path, self.format, self.template, self.segment_count, order=self.order
        )

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = TemplateValue('relation.field', 'html', "<text position=\"0\">, 1)
        >>> s.unwrap()
        'relation', TemplateValue('field', 'html', "<text position=\"0\">, 1)
        """
        base_path, *remaining_components = self.path.split(".")
        new_path = ".".join(remaining_components)
        return (
            base_path,
            TemplateValue(
                new_path,
                self.format,
                self.template,
                self.segment_count,
                order=self.order,
            ),
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
