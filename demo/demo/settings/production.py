import contextlib

from .base import *  # noqa: F403


DEBUG = False

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/6.0/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"]["BACKEND"] = (  # noqa: F405
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)

with contextlib.suppress(ImportError):
    from .local import *  # noqa: F403
