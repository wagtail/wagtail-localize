from bs4 import BeautifulSoup, NavigableString

from wagtail_localize.translation.segments.html import lstrip_keep, rstrip_keep

from .base import BaseMachineTranslator


def translate_string(string):
    # Preserve leading/trailing whitespace. This could be a segment of a sentence.
    string, left_whitespace = lstrip_keep(string)
    string, right_whitespace = rstrip_keep(string)

    words = string.split(' ')

    return left_whitespace + ' '.join(reversed(words)) + right_whitespace


def translate_html(html):
    soup = BeautifulSoup(html, 'html.parser')

    for tag in soup:
        if isinstance(tag, NavigableString):
            tag.string.replace_with(translate_string(tag.string))

    return str(soup)


class DummyTranslator(BaseMachineTranslator):
    def translate(self, source_locale, target_locale, strings):
        return {
            string: translate_html(string) for string in strings
        }

    def can_translate(self, source_locale, target_locale):
        return source_locale.language_code != target_locale.language_code
