import json

import requests

from wagtail_localize.machine_translators.base import BaseMachineTranslator
from wagtail_localize.strings import StringValue


class LibreTranslator(BaseMachineTranslator):
    """
    A machine translator that uses the LibreTranslate API.

    API Documentation:
        https://libretranslate.com/docs/
    """

    display_name = "LibreTranslate"

    def get_api_endpoint(self):
        return self.options["LIBRETRANSLATE_URL"]

    def get_timeout(self):
        return self.options.get("TIMEOUT", 10)

    def language_code(self, code):
        return code.split("-")[0]

    def translate(self, source_locale, target_locale, strings):
        translations = [item.data for item in list(strings)]
        response = requests.post(
            self.get_api_endpoint() + "/translate",
            data=json.dumps(
                {
                    "q": translations,
                    "source": self.language_code(source_locale.language_code),
                    "target": self.language_code(target_locale.language_code),
                    "api_key": self.options["API_KEY"],
                    "format": "html",
                }
            ),
            headers={"Content-Type": "application/json"},
            timeout=self.get_timeout(),
        )
        response.raise_for_status()

        return {
            string: StringValue(translation)
            for string, translation in zip(strings, response.json()["translatedText"])
        }

    def can_translate(self, source_locale, target_locale):
        return self.language_code(source_locale.language_code) != self.language_code(
            target_locale.language_code
        )
