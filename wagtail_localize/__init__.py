from django import VERSION as DJANGO_VERSION

from .version import get_version


if DJANGO_VERSION >= (3, 2):
    # The declaration is only needed for older Django versions
    pass
else:
    default_app_config = "wagtail_localize.apps.WagtailLocalizeAppConfig"


# release must be one of alpha, beta, rc, or final
VERSION = (1, 0, 1, "final", 1)

__version__ = get_version(VERSION)
