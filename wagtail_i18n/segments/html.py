from bs4 import BeautifulSoup


def extract_html_segment(html):
    soup = BeautifulSoup(html, 'html.parser')
    texts = []

    for descendant in soup.descendants:
        if descendant.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
            string = descendant.string

            if string:
                position = len(texts)
                texts.append(descendant.string)
                descendant.clear()
                descendant.append(soup.new_tag('text', position=position))

    return str(soup), texts


def render_html_segment(template, texts):
    soup = BeautifulSoup(template, 'html.parser')

    for text_element in soup.findAll('text'):
        value = texts[int(text_element.get('position'))]
        text_element.replaceWith(value)

    return str(soup)
