import warnings

import requests

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator


SUPPORTED_FORMALITY_OPTIONS = {"default", "prefer_less", "prefer_more"}


def language_code(code, *, is_target=False):
    # DeepL supports targeting Brazilian Portuguese and requires to specifically request American or British English.
    # @see https://www.deepl.com/en/docs-api/translate-text/translate-text
    upper_code = code.upper()
    if is_target and upper_code in ["PT-PT", "PT-BR", "EN-US", "EN-GB"]:
        return upper_code

    return upper_code.split("-")[0]


class DeepLTranslator(BaseMachineTranslator):
    display_name = "DeepL"

    def get_api_endpoint(self):
        if self.options.get("AUTH_KEY", "").endswith(":fx"):
            return "https://api-free.deepl.com/v2/translate"
        return "https://api.deepl.com/v2/translate"

    def get_parameters(self, source_locale, target_locale, strings):
        source_lang = language_code(source_locale.language_code)
        target_lang = language_code(target_locale.language_code, is_target=True)

        parameters = {
            "text": [string.data for string in strings],
            "tag_handling": "xml",
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

        if formality := self.options.get("FORMALITY"):
            if formality in SUPPORTED_FORMALITY_OPTIONS:
                parameters["formality"] = formality
            else:
                warnings.warn(
                    f"Unsupported formality option '{formality}'. "
                    f"Supported options are: {', '.join(SUPPORTED_FORMALITY_OPTIONS)}"
                )

        if glossaries := self.options.get("GLOSSARY_IDS"):
            lang_pair = (source_lang, target_lang)
            if glossary_id := glossaries.get(lang_pair):
                parameters["glossary_id"] = glossary_id
            else:
                warnings.warn(
                    f"No glossary defined for (source, target) pair: {lang_pair}"
                )

        return parameters

    def get_headers(self):
        return {
            "Authorization": f"DeepL-Auth-Key {self.options['AUTH_KEY']}",
        }

    def translate(self, source_locale, target_locale, strings):
        response = requests.post(
            self.get_api_endpoint(),
            self.get_parameters(source_locale, target_locale, strings),
            timeout=int(self.options.get("TIMEOUT", 30)),
            headers=self.get_headers(),
        )

        return {
            string: StringValue(translation["text"])
            for string, translation in zip(strings, response.json()["translations"])
        }

    def can_translate(self, source_locale, target_locale):
        return language_code(source_locale.language_code) != language_code(
            target_locale.language_code, is_target=True
        )
