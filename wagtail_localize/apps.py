from django.apps import AppConfig


class WagtailLocalizeAppConfig(AppConfig):
    name = 'wagtail_localize'
    label = 'wagtail_localize'
    verbose_name = "Wagtail localize"

    def ready(self):
        from .models import register_post_delete_signal_handlers
        register_post_delete_signal_handlers()
