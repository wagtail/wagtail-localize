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

    def translate(self, source_locale, target_locale, strings):
        parameters = {
            "auth_key": self.options["AUTH_KEY"],
            "text": [string.data for string in strings],
            "tag_handling": "xml",
            "source_lang": language_code(source_locale.language_code),
            "target_lang": language_code(target_locale.language_code, is_target=True),
        }

        if self.options.get("FORMALITY"):
            if self.options["FORMALITY"] in SUPPORTED_FORMALITY_OPTIONS:
                parameters["formality"] = self.options["FORMALITY"]
            else:
                warnings.warn(
                    f"Unsupported formality option '{self.options['FORMALITY']}'. Supported options are: {', '.join(SUPPORTED_FORMALITY_OPTIONS)}"
                )

        response = requests.post(
            self.get_api_endpoint(),
            parameters,
            timeout=30,
        )

        return {
            string: StringValue(translation["text"])
            for string, translation in zip(strings, response.json()["translations"])
        }

    def can_translate(self, source_locale, target_locale):
        return language_code(source_locale.language_code) != language_code(
            target_locale.language_code, is_target=True
        )
