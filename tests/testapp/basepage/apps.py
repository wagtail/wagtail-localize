from django.apps import AppConfig


class BasePageAppConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "tests.testapp.basepage"
