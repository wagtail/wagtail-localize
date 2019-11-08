from bs4 import BeautifulSoup, NavigableString


INLINE_TAGS = ["a", "abbr", "acronym", "b", "code", "em", "i", "strong"]


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


def extract_html_segments(html):
    """
    This function extracts translatable segments from an HTML fragment.

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
            return False

        has_block = False
        buffer = []

        for child in element.children:
            is_block = walk(child)

            if is_block:
                has_block = True

                if buffer:
                    wrap(buffer)
                    buffer = []

            else:
                buffer.append(child)

        if buffer and has_block:
            wrap(buffer)
            buffer = []

        if element.name not in INLINE_TAGS:
            if buffer:
                wrap(buffer)

            return True

        return False

    walk(soup)

    # Now extract segments from the <text> tags
    segments = []
    for element in soup.descendants:
        if element.name == "text":
            text = element.attrs.pop("value")

            # Strip leading and trailing whitespace. We keep the values and reinsert them
            # into the template
            # This is probably not necessary, but just to be on the safe side
            text, prefix = lstrip_keep(text)
            text, suffix = rstrip_keep(text)

            element.attrs["position"] = len(segments)
            segments.append(text.strip())

            if prefix:
                element.insert_before(prefix)

            if suffix:
                element.insert_after(suffix)

    return str(soup), segments


def restore_html_segments(template, segments):
    soup = BeautifulSoup(template, "html.parser")

    for text_element in soup.findAll("text"):
        value = segments[int(text_element.get("position"))]
        text_element.replaceWith(BeautifulSoup(value.strip(), "html.parser"))

    return str(soup)


def extract_html_elements(html):
    """
    Extracts HTML elements from a fragment. Returns the plain text representation
    of the HTML document and an array of elements including their span, type and attributes.

    For example:

    text, elements = extract_html_elements("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text")

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


def restore_html_elements(text, elements):
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
            current_element.append(text[cursor : element[0]])
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
