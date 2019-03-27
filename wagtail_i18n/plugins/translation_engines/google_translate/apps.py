from django.apps import AppConfig


class WagtailI18NGoogleTranslateAppConfig(AppConfig):
    label = 'wagtail_i18n_google_translate'
    name = 'wagtail_i18n.plugins.translation_engines.google_translate'
    verbose_name = "Wagtail I18N Google Translate translation engine"
