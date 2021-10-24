from bs4 import BeautifulSoup, NavigableString, Tag
from django.utils.translation import gettext_lazy as _

from wagtail_localize.strings import StringValue, lstrip_keep, rstrip_keep

from .base import BaseMachineTranslator


def language_code(code):
    return code.split("-")[0]


def translate_string(string):
    # Preserve leading/trailing whitespace. This could be a segment of a sentence.
    string, left_whitespace = lstrip_keep(string)
    string, right_whitespace = rstrip_keep(string)

    words = string.split(" ")

    return left_whitespace + " ".join(reversed(words)) + right_whitespace


def translate_html(html):
    soup = BeautifulSoup(html, "html.parser")

    def walk(soup):
        for child in soup.children:
            if isinstance(child, NavigableString):
                # Translate navigable strings
                child.string.replace_with(translate_string(child.string))

            else:
                walk(child)

    # Reverse the children
    if isinstance(soup, Tag):
        soup.contents.reverse()

    walk(soup)

    return str(soup)


class DummyTranslator(BaseMachineTranslator):
    display_name = _("Dummy translator")

    def translate(self, source_locale, target_locale, strings):
        return {string: StringValue(translate_html(string.data)) for string in strings}

    def can_translate(self, source_locale, target_locale):
        return language_code(source_locale.language_code) != language_code(
            target_locale.language_code
        )
