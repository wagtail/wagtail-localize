from bs4 import BeautifulSoup, NavigableString


INLINE_TAGS = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i', 'strong']


def lstrip_keep(text):
    """
    Like lstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.lstrip()
    prefix = text[0:(text_length-len(new_text))]
    return new_text, prefix


def rstrip_keep(text):
    """
    Like rstrip, but also returns the whitespace that was stripped off
    """
    text_length = len(text)
    new_text = text.rstrip()
    if text_length != len(new_text):
        suffix = text[-(text_length-len(new_text)):]
    else:
        suffix = ''
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
    soup = BeautifulSoup(html, 'html.parser')

    def wrap(elements):
        """
        Wraps the given elements with a <text> tag

        The elements must be contiguous siblings or this might screw up the tree.
        """
        value = ''.join(str(element) for element in elements)

        if value and not value.isspace():
            # Create <text> tag
            elements[0].insert_before(soup.new_tag('text', value=value))

            # Remove elements
            for element in elements:
                element.replaceWith('')

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
        if element.name == 'text':
            text = element.attrs.pop('value')

            # Strip leading and trailing whitespace. We keep the values and reinsert them
            # into the template
            # This is probably not necessary, but just to be on the safe side
            text, prefix = lstrip_keep(text)
            text, suffix = rstrip_keep(text)

            element.attrs['position'] = len(segments)
            segments.append(text.strip())

            if prefix:
                element.insert_before(prefix)

            if suffix:
                element.insert_after(suffix)

    return str(soup), segments


def restore_html_segments(template, texts):
    soup = BeautifulSoup(template, 'html.parser')

    for text_element in soup.findAll('text'):
        value = texts[int(text_element.get('position'))]
        text_element.replaceWith(value.strip())

    return str(soup)
