# This file contains a very lightweight implementation of RFC 72: Background workers (https://github.com/wagtail/rfcs/pull/72)
# This is only to be used by Wagtail Localize and will be replaced with the full Wagtail implementation later

from django.conf import settings
from django.utils.module_loading import import_string


class BaseJobBackend:
    def __init__(self, options):
        pass

    def enqueue(self, func, args, kwargs):
        raise NotImplementedError()


class ImmediateBackend(BaseJobBackend):
    def enqueue(self, func, args, kwargs):
        func(*args, **kwargs)


def get_backend():
    config = getattr(
        settings,
        "WAGTAILLOCALIZE_JOBS",
        {"BACKEND": "wagtail_localize.tasks.ImmediateBackend"},
    )
    backend_class = import_string(config["BACKEND"])
    return backend_class(config.get("OPTIONS", {}))


background = get_backend()