from django import VERSION as DJANGO_VERSION


if DJANGO_VERSION >= (3, 2):
    # The declaration is only needed for older Django versions
    pass
else:
    default_app_config = "wagtail_localize.locales.apps.WagtailLocalesAppConfig"
