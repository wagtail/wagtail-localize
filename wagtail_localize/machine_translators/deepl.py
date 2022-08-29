import requests

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator


def language_code(code, is_target=False):
    # DeepL supports targeting Brazillian Portuguese but doesn't have this for other languages
    if is_target and code in ["pt-pt", "pt-br"]:
        return code

    return code.split("-")[0].upper()

def auth_key_is_free_account(auth_key: str) -> bool:
    # https://github.com/DeepLcom/deepl-python/blob/main/deepl/util.py
    """Returns True if the given authentication key belongs to a DeepL API Free
    account, otherwise False."""
    return auth_key.endswith(":fx")


class DeepLTranslator(BaseMachineTranslator):
    display_name = "DeepL"
    _DEEPL_SERVER_URL = "https://api.deepl.com/v2/translate"
    _DEEPL_SERVER_URL_FREE = "https://api-free.deepl.com/v2/translate"
    
    def translate(self, source_locale, target_locale, strings):
        server_url = self._DEEPL_SERVER_URL_FREE if auth_key_is_free_account(auth_key) else self._DEEPL_SERVER_URL
        response = requests.post(
            server_url,
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

        return {
            string: StringValue(translation["text"])
            for string, translation in zip(strings, response.json()["translations"])
        }

    def can_translate(self, source_locale, target_locale):
        return language_code(source_locale.language_code) != language_code(
            target_locale.language_code, is_target=True
        )
