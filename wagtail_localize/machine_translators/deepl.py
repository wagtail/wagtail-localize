import requests

from http import HTTPStatus

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator

class ApiEndpointError(Exception):

    def __init__(self, code, reason, message="Unspecified Deepl API error ocurred"):
        self.code = code
        self.reason = reason
        self.message = message
        super().__init__(f"{self.code}: [{self.reason}] {self.message}")


def language_code(code, is_target=False):
    # DeepL supports targeting Brazillian Portuguese but doesn't have this for other languages
    if is_target and code in ["pt-pt", "pt-br"]:
        return code

    return code.split("-")[0].upper()


class DeepLTranslator(BaseMachineTranslator):
    display_name = "DeepL"

    def translate(self, source_locale, target_locale, strings):
        api_endpoint = "https://api.deepl.com/v2/translate"
        if "API_ENDPOINT" in self.options:
            api_endpoint = self.options["API_ENDPOINT"]
        response = requests.post(
            api_endpoint,
            {
                "auth_key": self.options["AUTH_KEY"],
                "text": [string.data for string in strings],
                "tag_handling": "xml",
                "source_lang": language_code(source_locale.language_code),
                "target_lang": language_code(
                    target_locale.language_code, is_target=True
                ),
            },
        )

        if response.status_code != HTTPStatus.OK:
            raise ApiEndpointError(response.status_code, response.reason, response.text)

        return {
            string: StringValue(translation["text"])
            for string, translation in zip(strings, response.json()["translations"])
        }

    def can_translate(self, source_locale, target_locale):
        return language_code(source_locale.language_code) != language_code(
            target_locale.language_code, is_target=True
        )
