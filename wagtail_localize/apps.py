from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WagtailLocalizeAppConfig(AppConfig):
    name = 'wagtail_localize'
    label = 'wagtail_localize'
    verbose_name = _("Wagtail localize")

    def ready(self):
        from .models import register_post_delete_signal_handlers
        register_post_delete_signal_handlers()
