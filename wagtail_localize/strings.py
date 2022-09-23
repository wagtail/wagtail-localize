from collections import Counter

from bs4 import BeautifulSoup, NavigableString, Tag
from django.utils.html import escape
from django.utils.translation import gettext as _


# List of tags that are allowed in segments
INLINE_TAGS = ["a", "abbr", "acronym", "b", "code", "em", "i", "strong", "br"]


def lstrip_keep(text):
    """
    Like lstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.lstrip()
    prefix = text[0 : (text_length - len(new_text))]
    return new_text, prefix


def rstrip_keep(text):
    """
    Like rstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.rstrip()
    if text_length != len(new_text):
        suffix = text[-(text_length - len(new_text)) :]
    else:
        suffix = ""
    return new_text, suffix


def validate_element(element):
    """
    Checks the given BeautifulSoup element for anything that we disallow from strings.
    """
    if isinstance(element, NavigableString):
        return

    # Validate tag and attributes
    if isinstance(element, Tag) and element.name != "[document]":
        # Block tags are not allowed in strings
        if element.name not in INLINE_TAGS:
            raise ValueError(
                _(
                    "<{}> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)"
                ).format(element.name)
            )

        # Elements can't have attributes, except for <a> tags
        keys = set(element.attrs.keys())
        if element.name == "a" and "id" in keys:
            keys.remove("id")
        if keys:
            raise ValueError(
                _(
                    "Strings cannot have any HTML tags with attributes (except for 'id' in <a> tags)"
                )
            )

    # Traverse children
    for child_element in element.children:
        validate_element(child_element)


class StringValue:
    """
    A fragment of HTML that only contains inline tags with all attributes stripped out.

    Attributes:
        data (str): The HTML fragment.
    """

    def __init__(self, data):
        self.data = data

    @classmethod
    def from_plaintext(cls, text):
        """
        Initialises a StringValue from a plain text string.

        Args:
            text (str): The plain text to turn into a StringValue.

        Returns:
            StringValue: The initialised StringValue.
        """
        # Escapes all HTML characters and replaces newlines with <br> tags
        elements = []

        for line in text.split("\n"):
            if line:
                elements.append(escape(line))

            elements.append("<br>")

        # Remove last element which is an extra br tag
        elements.pop()

        # Join the elements then pass through beautiful soup to normalize the HTML
        return cls(str(BeautifulSoup("".join(elements), "html.parser")))

    @classmethod
    def from_source_html(cls, html):
        """
        Initialises a StringValue from a HTML string.

        Source HTML is the HTML you get in Wagtail field data. This contains HTML attributes that
        must first be stripped out before the string can be translated.

        Args:
            html (str): The HTML to turn into a StringValue.

        Returns:
            tuple[StringValue, dict]: The initialised StringValue and a dictionary of extracted HTML attributes.
        """
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
                        element.attrs = {"id": element_id}

                    # Traverse into element children
                    walk(element)

        walk(soup)

        validate_element(soup)

        return cls(str(soup)), attrs

    @classmethod
    def from_translated_html(cls, html):
        """
        Initialises a StringValue from a HTML string.

        HTML attributes are stripped out before translation, so translated HTML does not
        need to have them stripped out.

        Args:
            html (str): The HTML to turn into a StringValue.

        Returns:
            StringValue: The initialised StringValue.
        """
        soup = BeautifulSoup(html, "html.parser")

        validate_element(soup)

        return cls(str(soup))

    def render_text(self):
        """
        Returns a plain text representation of the string.

        Note: If the string was initialised from HTML, all HTML tags will be stripped out.

        Returns:
            str: The plain text representation of the string.
        """
        soup = BeautifulSoup(self.data, "html.parser")
        texts = []

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    texts.append(element)

                elif element.name == "br":
                    texts.append("\n")

                else:
                    walk(element)

        walk(soup)

        return "".join(texts)

    def render_soup(self, attrs):
        """
        Returns a BeautifulSoup instance containing the string.

        This is equivalent to: ``BeautifulSoup(string.render_html(attrs), "html.parser")``

        The .render_html() method calls this internally so it would be more performant to call this directly if a
        BeautifulSoup object is what you need.

        Returns:
            BeautifulSoup: A BeautifulSoup object representing the HTML of the string.
        """
        soup = BeautifulSoup(self.data, "html.parser")

        def walk(soup):
            for element in soup.children:
                if isinstance(element, NavigableString):
                    pass

                else:
                    # Restore HTML attributes
                    if "id" in element.attrs:
                        element.attrs = attrs[element.attrs["id"]]

                    # Traverse into element children
                    walk(element)

        walk(soup)

        return soup

    def render_html(self, attrs):
        """
        Returns a HTML representation of the string.

        Note: If the string was initialised from plain text, all special characters will be escaped.

        Returns:
            str: The HTML representation of the string.
        """
        return str(self.render_soup(attrs))

    def get_translatable_html(self):
        """
        Returns a HTML string without restoring any HTML attributes.

        Note: If the string was initialised from plain text, all special characters will be escaped.

        Returns:
            str: The HTML representation of the string without HTML attributes
        """
        return self.data

    def __eq__(self, other):
        return isinstance(other, StringValue) and other.data == self.data

    def __repr__(self):
        return "<StringValue '{}'>".format(self.data)

    def __hash__(self):
        return hash(self.data)


def extract_strings(html):
    """
    This function extracts translatable strings from an HTML fragment.

    Inline elements and visible text are extracted together.

    This also returns a list of hrefs that were found in the HTML, these are also included in the strings.

    For example:

        <h1>Foo</h1>
        <p>
            Bar
            <ul>
                <li><b>Baz</b></li>
            </ul>
            <a href="http://example.com">A link</a>
        </p>

    Will produce the following two outputs (as a 3-tuple)

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
            "<a href="http://example.com">A link</a>"
        ]

    Args:
        html (str): The HTML to extract strings from.

    Returns:
        tuple[str, list[tuple[StringValue, dict]]]: Returns a template string, and list 2-tuples containing a
            StringValue and dict of HTML attribute
    """
    if html is None:
        html = ""

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
            and elements[0].name != "a"  # keep href translatable
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
    position = 0
    for element in soup.descendants:
        if element.name == "text":
            text = element.attrs.pop("value")

            # Strip leading and trailing whitespace. We keep the values and reinsert them
            # into the template
            # This is probably not necessary, but just to be on the safe side
            text, prefix = lstrip_keep(text)
            text, suffix = rstrip_keep(text)

            element.attrs["position"] = position
            position += 1
            string_val, attrs = StringValue.from_source_html(text)
            strings.append((string_val, attrs))

            if prefix:
                element.insert_before(prefix)

            if suffix:
                element.insert_after(suffix)

    return str(soup), strings


def restore_strings(template, strings):
    """
    Inserts a list of strings into the template.

    This reverses the `extract_strings` function.

    Args:
        template (str): The HTML template.
        strings (list[tuple[StringValue, dict]]): A list of 2-tuples containing a StringValue and HTML attributes dict
            for each string to reinsert into the template.

    Returns:
        str: A HTML blob with the strings inserted into the template.
    """
    soup = BeautifulSoup(template, "html.parser")
    for text_element in soup.findAll("text"):
        string, attrs = strings[int(text_element.get("position"))]
        text_element.replaceWith(string.render_soup(attrs))

    return str(soup)


def extract_ids(template):
    """Extract link ids from one template string and return it in a set."""
    soup = BeautifulSoup(template, "html.parser")
    ids = set()
    for element in soup.descendants:
        if not isinstance(element, Tag):
            continue

        if element.name == "a":
            if "id" in element.attrs:
                ids.add(element.attrs["id"])

    return ids


def validate_translation_links(translation_of, data):
    """Check that the link id in a translation are present in its source."""
    id1s, id2s = extract_ids(translation_of), extract_ids(data)
    new_ids = id2s - id1s
    if new_ids:
        ids = ", ".join(sorted(new_ids))
        raise ValueError(_("Unrecognised id found in an <a> tag: {}").format(ids))
