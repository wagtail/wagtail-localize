from django.apps import AppConfig


class WagtailTranslationPOFileAppConfig(AppConfig):
    label = 'wagtail_translation_pofile'
    name = 'wagtail_translation.engines.pofile'
    verbose_name = "Wagtail Translation PO-file engine"
