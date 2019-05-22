from django.apps import AppConfig


class WagtailTranslationGoogleTranslateAppConfig(AppConfig):
    label = 'wagtail_translation_google_translate'
    name = 'wagtail_translation.engines.google_translate'
    verbose_name = "Wagtail Translation Google Translate engine"
