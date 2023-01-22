from django.utils.functional import cached_property
from google.cloud import translate
from google.oauth2 import service_account

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator


class GoogleCloudTranslator(BaseMachineTranslator):
    display_name = "Google Translate"

    @cached_property
    def client(self):
        # use CREDENTIALS dict, if supplied
        credentials = self.options.get("CREDENTIALS")
        if credentials:
            return translate.TranslationServiceClient(
                credentials=service_account.Credentials.from_service_account_info(
                    credentials
                )
            )
        # load key from 'CREDENTIALS_PATH', if supplied
        path = self.options.get("CREDENTIALS_PATH")
        if path:
            return translate.TranslationServiceClient(
                credentials=service_account.Credentials.from_service_account_file(path)
            )
        # load key from env["GOOGLE_APPLICATION_CREDENTIALS"]
        return translate.TranslationServiceClient()

    def translate(self, source_locale, target_locale, strings):
        project_id = self.options["PROJECT_ID"]
        location = self.options.get("LOCATION", "global")

        response = self.client.translate_text(
            request={
                "parent": f"projects/{project_id}/locations/{location}",
                "contents": [string.data for string in strings],
                "mime_type": "text/html",
                "source_language_code": source_locale.language_code,
                "target_language_code": target_locale.language_code,
            }
        )

        return {
            string: StringValue(translation.translated_text)
            for string, translation in zip(strings, response.translations)
        }

    def can_translate(self, source_locale, target_locale):
        return source_locale.language_code != target_locale.language_code
