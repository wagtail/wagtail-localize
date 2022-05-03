# This file contains a very lightweight implementation of RFC 72: Background workers (https://github.com/wagtail/rfcs/pull/72)
# This is only to be used by Wagtail Localize and will be replaced with the full Wagtail implementation later

from typing import Any, Callable

from django.conf import settings
from django.utils.module_loading import import_string
from typing_extensions import ParamSpec


P = ParamSpec("P")


class BaseJobBackend:
    def __init__(self, options):
        pass

    def enqueue(self, func: Callable[P, Any], args: P.args, kwargs: P.kwargs):
        raise NotImplementedError()


class ImmediateBackend(BaseJobBackend):
    def enqueue(self, func: Callable[P, Any], args: P.args, kwargs: P.kwargs):
        func(*args, **kwargs)


class DjangoRQJobBackend(BaseJobBackend):
    def __init__(self, options):
        import django_rq

        self.queue = django_rq.get_queue(options.get("QUEUE", "default"))

    def enqueue(self, func: Callable[P, Any], args: P.args, kwargs: P.kwargs):
        self.queue.enqueue(func, *args, **kwargs)


def get_backend():
    config = getattr(
        settings,
        "WAGTAILLOCALIZE_JOBS",
        {"BACKEND": "wagtail_localize.tasks.ImmediateBackend"},
    )
    backend_class = import_string(config["BACKEND"])
    return backend_class(config.get("OPTIONS", {}))


background: BaseJobBackend = get_backend()
