from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WagtailLocalesAppConfig(AppConfig):
    name = 'wagtail_localize.locales'
    label = 'wagtaillocales'
    verbose_name = _("Wagtail locales (Wagtail Localize version)")
