from google.cloud import translate

from wagtail_localize.strings import StringValue

from .base import BaseMachineTranslator


class GoogleCloudTranslator(BaseMachineTranslator):
    display_name = "Google Translate"

    def translate(self, source_locale, target_locale, strings):
        client = translate.TranslationServiceClient()
        project_id = self.options["PROJECT_ID"]
        location = self.options.get("LOCATION", "global")

        response = client.translate_text(
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
