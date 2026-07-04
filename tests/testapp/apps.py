from django.apps import AppConfig


class WagtailLocalizeTestAppConfig(AppConfig):
    label = "wagtail_localize_test"
    name = "tests.testapp"
    verbose_name = "Wagtail Localize Test app"
    default_auto_field = "django.db.models.AutoField"
