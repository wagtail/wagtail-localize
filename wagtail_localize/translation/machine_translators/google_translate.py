from wagtail_localize.translation.strings import StringValue

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
    def translate(self, source_locale, target_locale, strings):
        translator = googletrans.Translator()
        google_translations = translator.translate(
            [string.render_text() for string in strings],
            src=language_code(source_locale.language_code),
            dest=language_code(target_locale.language_code),
        )

        return {
            StringValue.from_plaintext(translation.origin): StringValue.from_plaintext(translation.text) for translation in google_translations
        }

    def can_translate(self, source_locale, target_locale):
        return source_locale.language_code != target_locale.language_code
