from django.apps import AppConfig


class WagtailLocalizeGoogleTranslateAppConfig(AppConfig):
    label = "wagtail_localize_google_translate"
    name = "wagtail_localize.translation_engines.google_translate"
    verbose_name = "Wagtail Localize Google Translate translation engine"
