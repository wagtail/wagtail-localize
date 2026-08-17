from django.apps import AppConfig


class WagtailLocalizeAppConfig(AppConfig):
    name = "wagtail_localize"
    label = "wagtail_localize"
    verbose_name = "Wagtail localize"
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from .models import register_post_delete_signal_handlers

        register_post_delete_signal_handlers()
