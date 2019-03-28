from django.apps import AppConfig


class WagtailI18NPOFileAppConfig(AppConfig):
    label = 'wagtail_i18n_pofile'
    name = 'wagtail_i18n.plugins.translation_engines.pofile'
    verbose_name = "Wagtail I18N PO file translation engine"
