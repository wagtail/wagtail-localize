from django.apps import AppConfig


class WagtailLocalizePOFileAppConfig(AppConfig):
    label = "wagtail_localize_pofile"
    name = "wagtail_localize.translation_engines.pofile"
    verbose_name = "Wagtail Localize PO file translation engine"
