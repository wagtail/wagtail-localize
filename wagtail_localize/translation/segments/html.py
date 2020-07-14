from collections import Counter

from bs4 import BeautifulSoup, NavigableString
from django.forms.utils import flatatt
from django.utils.html import escape


# List of tags that are allowed in HTML snippets
INLINE_TAGS = ["a", "abbr", "acronym", "b", "code", "em", "i", "strong", "br"]


def lstrip_keep(text):
    """
    Like lstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.lstrip()
    prefix = text[0:(text_length - len(new_text))]
    return new_text, prefix


def rstrip_keep(text):
    """
    Like rstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.rstrip()
    if text_length != len(new_text):
        suffix = text[-(text_length - len(new_text)):]
    else:
        suffix = ""
    return new_text, suffix


def extract_html_snippets(html):
    """
    This function extracts translatable snippets from an HTML fragment.

    Inline elements and visible text are extracted together.

    For example:

        <h1>Foo</h1>
        <p>
            Bar
            <ul>
                <li><b>Baz</b></li>
            </ul>
        </p>

    Will produce the following two outputs (as a 2-tuple)

        <h1><text position="0"></h1>
        <p>
            <text position="1">
            <ul>
                <li><text position="2"></li>
            </ul>
        </p>

        [
            HTMLSnippet("Foo"),
            HTMLSnippet("Bar"),
            HTMLSnippet("<b>Baz</b>"),
        ]
    """
    soup = BeautifulSoup(html, "html.parser")

    def wrap(elements):
        """
        Wraps the given elements with a <text> tag

        The elements must be contiguous siblings or this might screw up the tree.
        """
        elements = list(elements)

        # Skip if there are no tags to wrap
        # We can get here after filters below have been applied
        if len(elements) == 0:
            return

        # If there is a single element and that is an inline tag, wrap just the contents.
        # We only care about inline tags that wrap only part of a snippet
        if (
            len(elements) == 1
            and not isinstance(elements[0], NavigableString)
            and elements[0].name in INLINE_TAGS
        ):
            wrap(elements[0].children)
            return

        def ignore_if_at_end(element):
            """
            Returns True if the given element should be ignored if it is at one of the ends
            """
            if isinstance(element, NavigableString):
                return False

            # Ignore if there are no text nodes
            # This will exclude both <br> tags and empty inline tags
            if not any(
                isinstance(desc, NavigableString) for desc in element.descendants
            ):
                return True

            return False

        if ignore_if_at_end(elements[0]):
            wrap(elements[1:])
            return

        if ignore_if_at_end(elements[-1]):
            wrap(elements[:-1])
            return

        value = "".join(
            element.output_ready()
            if isinstance(element, NavigableString)
            else str(element)
            for element in elements
        )

        if value and not value.isspace():
            # Create <text> tag
            elements[0].insert_before(soup.new_tag("text", value=value))

            # Remove elements
            for element in elements:
                element.replaceWith("")

    def walk(element):
        """
        Walks the tree in depth first search post-order.

        When it encounters an element that could be extracted, it wraps it with
        a <text> tag. These are extracted in the next stage (because we want to
        preserve order of occurance).

        For example:

        <p>
            Foo
            <ul>
              <li>Bar</li>
            </ul>
            Baz
        </p>

        Is transformed to:

        <p>
            <text>Foo</text>
            <ul>
              <li><text><b>Bar</b></text></li>
            </ul>
            <text>Baz</text>
        </p>
        """
        if isinstance(element, NavigableString):
            return False, False

        has_block = False
        has_wrap = False
        buffer = []

        for child in element.children:
            child_has_wrap, is_block = walk(child)

            if child_has_wrap:
                has_wrap = True

            if is_block:
                has_block = True

                if buffer:
                    wrap(buffer)
                    buffer = []
                    has_wrap = True

            else:
                if not child_has_wrap:
                    buffer.append(child)

        if buffer and has_block:
            wrap(buffer)
            buffer = []
            has_wrap = True

        if element.name not in INLINE_TAGS:
            if buffer:
                wrap(buffer)
                has_wrap = True

            return has_wrap, True

        return has_wrap, False

    walk(soup)

    # Now extract snippets from the <text> tags
    snippets = []
    for element in soup.descendants:
        if element.name == "text":
            text = element.attrs.pop("value")

            # Strip leading and trailing whitespace. We keep the values and reinsert them
            # into the template
            # This is probably not necessary, but just to be on the safe side
            text, prefix = lstrip_keep(text)
            text, suffix = rstrip_keep(text)

            element.attrs["position"] = len(snippets)
            snippets.append(HTMLSnippet.from_html(text.strip()))

            if prefix:
                element.insert_before(prefix)

            if suffix:
                element.insert_after(suffix)

    return str(soup), snippets


def restore_html_snippets(template, snippets):
    soup = BeautifulSoup(template, "html.parser")

    for text_element in soup.findAll("text"):
        snippet = snippets[int(text_element.get("position"))]
        text_element.replaceWith(BeautifulSoup(snippet.html, "html.parser"))

    return str(soup)


class HTMLSnippet:
    class Entity:
        """
        Represents the position of an inline entity in a HTML snippet

        These are used to track how inline elements such as text formatting
        and links should be moved in translated versions of a snippet.

        The parameters are as follows:

        - start/end are the character offsets in the original text that this element appears
        they may be equal but end must not be less than start.
        For example, to select just the first character, the start and end offsets with be 0,1
        respectively.
        - identifier is a number that is generated from the snippet extractor. It must be conserved
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
            if not isinstance(other, HTMLSnippet.Entity):
                return False

            return (
                self.start == other.start
                and self.end == other.end
                and self.identifier == other.identifier
                and self.element == other.element
            )

        def __repr__(self):
            return f"<HTMLSnippet.Entity {self.identifier} '{self.element_tag}' at [{self.start}:{self.end}]>"

    @staticmethod
    def _extract_html_entities(html):
        """
        Extracts HTML elements from a snippet. Returns the plain text representation
        of the HTML document and an array of elements including their span, type and attributes.

        For example:

        text, elements = extract_html_entities("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text")

        text == "This is a paragraph. This is some bold and now italic text"
        elements == [(39, 53, 'i', {}), (21, 53, 'b', {})]
        """
        soup = BeautifulSoup(html, "html.parser")

        texts = []
        cursor = {"current": 0}
        elements = []

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    texts.append(element)
                    cursor["current"] += len(element)

                else:
                    start = cursor["current"]
                    walk(element)
                    end = cursor["current"]

                    elements.append((start, end, element.name, element.attrs.copy()))

        walk(soup)

        return "".join(texts), elements

    @staticmethod
    def _restore_html_entities(text, elements):
        """
        Inserts elements into a plain text string returning a HTML document.
        """
        soup = BeautifulSoup("", "html.parser")
        stack = []
        cursor = 0
        current_element = soup

        # Sort elements by start position
        elements.sort(key=lambda element: element[0])

        for i, element in enumerate(elements):
            if cursor < element[0]:
                # Output text and advance cursor
                current_element.append(text[cursor:element[0]])
                cursor = element[0]

            stack.append((element[1], current_element))
            new_element = soup.new_tag(element[2], **element[3])
            current_element.append(new_element)
            current_element = new_element

            # Close existing elements before going to the next element
            while stack:
                if i < len(elements) - 1:
                    if stack[len(stack) - 1][0] > elements[i + 1][0]:
                        # New element created before this one closes.
                        # Go to next element
                        break

                element_end, previous_element = stack.pop()

                if cursor < element_end:
                    # Output text and advance cursor
                    current_element.append(text[cursor:element_end])
                    cursor = element_end

                current_element = previous_element

        if cursor < len(text):
            current_element.append(text[cursor:])

        return str(soup)

    def __init__(self, text, entities=None):
        self.text = text
        self.entities = entities

    @classmethod
    def from_plaintext(cls, text):
        return cls(text)

    @classmethod
    def from_html(cls, html):
        text, elements = cls._extract_html_entities(html)

        entities = []
        counter = Counter()
        for start, end, element_type, element_attrs in elements:
            counter[element_type] += 1
            identifier = element_type + str(counter[element_type])

            entities.append(
                cls.Entity(start, end, identifier, (element_type, element_attrs))
            )

        return cls(text, entities)

    @property
    def html(self):
        if not self.entities:
            return escape(self.text)

        return self._restore_html_entities(
            self.text,
            [(e.start, e.end, e.element[0], e.element[1]) for e in self.entities],
        )

    @property
    def html_with_ids(self):
        if not self.entities:
            return escape(self.text)

        return self._restore_html_entities(
            self.text,
            [
                (
                    e.start,
                    e.end,
                    e.element[0],
                    {"id": e.identifier} if e.element[1] else {},
                )
                for e in self.entities
            ],
        )

    def get_html_attrs(self):
        """
        Returns a mapping of html element identifiers to their attributes.

        For example, running this on the following snippet:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>

        Would return the following dictionary:

            {
                "a#a1": {"href": "https://mysite.com"}
            }
        """
        return {
            f"{e.element[0]}#{e.identifier}": e.element[1]
            for e in self.entities or []
            if e.element[1]
        }

    def replace_html_attrs(self, attrs_map):
        """
        Replaces the attributes of the HTML elements in this snippet with
        attributes in the provided mapping.

        This is used to overwrite any HTML attribute changes made to
        translated snippets so they are guarenteed to not be altered by
        translators.

        For example, running this on the following snippet:

            <b>Foo <a id="a1" href="https://badsite.com">Bar</a></b>

        With the following attrs_map:

            {
                "a#a1": {"href": "https://mysite.com"}
            }

        Would return the following snippet:

            <b>Foo <a id="a1" href="https://mysite.com">Bar</a></b>
        """
        for e in self.entities:
            key = f"{e.element[0]}#{e.identifier}"
            if key in attrs_map:
                e.element = (e.element[0], attrs_map[key])

    def is_empty(self):
        return self.html in ["", None]

    def __eq__(self, other):
        return (
            isinstance(other, HTMLSnippet)
            and self.html == other.html
        )

    def __repr__(self):
        return '<HTMLSnippet "{}">'.format(self.html)
