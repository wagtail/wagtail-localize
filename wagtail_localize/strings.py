from collections import Counter

from django.utils.html import escape

from bs4 import BeautifulSoup, NavigableString


# List of tags that are allowed in segments
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


class StringValue:
    """
    A fragment of HTML that only contains inline tags with all attributes stripped out.
    """
    def __init__(self, data):
        self.data = data

    @classmethod
    def from_plaintext(cls, text):
        # Escapes all HTML characters and replaces newlines with <br> tags
        elements = []

        for line in text.split('\n'):
            if line:
                elements.append(escape(line))

            elements.append('<br>')

        # Remove last element which is an extra br tag
        elements.pop()

        return cls(''.join(elements))

    @classmethod
    def from_html(cls, html):
        # Extracts attributes from any tags (eg, href from <a> tags) and stores a version
        # with just the translatable HTML
        soup = BeautifulSoup(html, "html.parser")
        attrs = {}
        counter = Counter()

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    pass

                else:
                    # Extract HTML attributes replacing them with an ID
                    if element.attrs:
                        counter[element.name] += 1
                        element_id = element.name + str(counter[element.name])
                        attrs[element_id] = element.attrs
                        element.attrs = {
                            'id': element_id
                        }

                    # Traverse into element children
                    walk(element)

        walk(soup)

        return cls(str(soup)), attrs

    def render_text(self):
        soup = BeautifulSoup(self.data, "html.parser")
        texts = []

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    texts.append(element)

                elif element.name == 'br':
                    texts.append('\n')

                else:
                    walk(element)

        walk(soup)

        return "".join(texts)

    def render_soup(self, attrs):
        soup = BeautifulSoup(self.data, "html.parser")

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    pass

                else:
                    # Restore HTML attributes
                    if 'id' in element.attrs:
                        element.attrs = attrs[element.attrs['id']]

                    # Traverse into element children
                    walk(element)

        walk(soup)

        return soup

    def render_html(self, attrs):
        return str(self.render_soup(attrs))

    def __eq__(self, other):
        return (
            isinstance(other, StringValue)
            and other.data == self.data
        )

    def __repr__(self):
        return "<StringValue '{}'>".format(self.data)

    def __hash__(self):
        return hash(self.data)


def extract_strings(html):
    """
    This function extracts translatable strings from an HTML fragment.

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
            "Foo",
            "Bar",
            "<b>Baz</b>",
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
        # We only care about inline tags that wrap only part of a segment
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

    # Now extract strings from the <text> tags
    strings = []
    for element in soup.descendants:
        if element.name == "text":
            text = element.attrs.pop("value")

            # Strip leading and trailing whitespace. We keep the values and reinsert them
            # into the template
            # This is probably not necessary, but just to be on the safe side
            text, prefix = lstrip_keep(text)
            text, suffix = rstrip_keep(text)

            element.attrs["position"] = len(strings)
            strings.append(StringValue.from_html(text))

            if prefix:
                element.insert_before(prefix)

            if suffix:
                element.insert_after(suffix)

    return str(soup), strings


def restore_strings(template, strings):
    soup = BeautifulSoup(template, "html.parser")

    for text_element in soup.findAll("text"):
        string, attrs = strings[int(text_element.get("position"))]
        text_element.replaceWith(string.render_soup(attrs))

    return str(soup)
