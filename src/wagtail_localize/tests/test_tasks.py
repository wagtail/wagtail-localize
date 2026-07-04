from unittest import mock

from django.test import TestCase, override_settings

from wagtail_localize.tasks import get_backend


@override_settings(
    WAGTAILLOCALIZE_JOBS={
        "BACKEND": "wagtail_localize.tasks.DjangoRQJobBackend",
        "OPTIONS": {"queue": "test_queue"},
    }
)
@mock.patch("django_rq.get_queue")
class TestDjangoRQBackend(TestCase):
    def test_enqueue_with_django_rq(self, get_queue):
        backend = get_backend()
        backend.enqueue(print, ["Hello world!"], {"end": "\r\n"})

        get_queue.assert_called_with("default")
        get_queue().enqueue.assert_called_with(print, "Hello world!", end="\r\n")
