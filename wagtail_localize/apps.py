from django.apps import AppConfig


class WagtailLocalizeAppConfig(AppConfig):
    label = "wagtail_localize"
    name = "wagtail_localize"
    verbose_name = "Wagtail Localize"

    def ready(self):
        # Import to register signal handlers
        from . import synctree
