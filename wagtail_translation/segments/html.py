from bs4 import BeautifulSoup, NavigableString


def extract_html_segment(html):
    soup = BeautifulSoup(html, 'html.parser')
    texts = []
    replacements = []

    for descendant in soup.descendants:
        if isinstance(descendant, NavigableString):
            string = descendant.strip()

            if string:
                position = len(texts)
                texts.append(descendant.string)
                replacements.append((descendant, soup.new_tag('text', position=position)))

    for descendant, replacement in replacements:
        descendant.replaceWith(replacement)

    return str(soup), texts


def render_html_segment(template, texts):
    soup = BeautifulSoup(template, 'html.parser')

    for text_element in soup.findAll('text'):
        value = texts[int(text_element.get('position'))]
        text_element.replaceWith(value)

    return str(soup)
