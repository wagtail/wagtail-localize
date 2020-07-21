from django.utils.translation import gettext_lazy as _

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator

# TODO: Switch to official Google API client
import googletrans


def language_code(code):
    if code in ["zh-hans", "zh-cn"]:
        return "zh-cn"

    if code in ["zh-hant", "zh-tw"]:
        return "zh-tw"

    return code.split("-")[0]


class GoogleTranslateTranslator(BaseMachineTranslator):
    display_name = _("Google Translate")

    def translate(self, source_locale, target_locale, strings):
        translator = googletrans.Translator()
        google_translations = translator.translate(
            [string.render_text() for string in strings],
            src=language_code(source_locale.language_code),
            dest=language_code(target_locale.language_code),
        )

        translations = {
            translation.origin: translation.text
            for translation in google_translations
        }

        return {
            string: StringValue.from_plaintext(translations[string.render_text()]) for string in strings
        }

    def can_translate(self, source_locale, target_locale):
        return source_locale.language_code != target_locale.language_code
