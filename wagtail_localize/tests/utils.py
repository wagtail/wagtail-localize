from django.contrib import messages
from django.urls import reverse

from wagtail_localize.test.models import TestPage


def assert_permission_denied(self, response):
    # Checks for Wagtail's permission denied response
    self.assertRedirects(response, reverse("wagtailadmin_home"))

    raised_messages = [
        (message.level_tag, message.message)
        for message in messages.get_messages(response.wsgi_request)
    ]
    self.assertIn(
        ("error", "Sorry, you do not have permission to access this area.\n\n\n\n\n"),
        raised_messages,
    )


def make_test_page(parent, cls=None, **kwargs):
    cls = cls or TestPage
    kwargs.setdefault("title", "Test page")
    return parent.add_child(instance=cls(**kwargs))
