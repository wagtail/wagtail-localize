from bs4 import BeautifulSoup


class HTMLSegmentFormatter:
    def parse(self, text, emit_segment):
        soup = BeautifulSoup(text, 'html.parser')
        texts = []

        for descendant in soup.descendants:
            if descendant.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
                string = descendant.string

                if string:
                    position = emit_segment(descendant.string)
                    descendant.clear()
                    descendant.append(soup.new_tag('text', position=position))

        return str(soup)

    def render(self, template, texts):
        soup = BeautifulSoup(template, 'html.parser')

        for text_element in soup.findAll('text'):
            value = texts[int(text_element.get('position'))]
            text_element.replaceWith(value)

        return str(soup)
