from .version import get_version


default_app_config = 'wagtail_localize.apps.WagtailLocalizeAppConfig'


# release must be one of alpha, beta, rc, or final
VERSION = (1, 0, 0, 'rc', 3)

__version__ = get_version(VERSION)
