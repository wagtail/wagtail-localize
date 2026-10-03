from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from wagtail import VERSION as WAGTAIL_VERSION


if settings.USE_CUSTOM_PAGE_MODEL:
    from tests.testapp.testpages_custombasepage.models import (
        TestPage,
    )
else:
    from tests.testapp.testpages_default.models import (
        TestPage,
    )


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


def get_page_ptr_accessor_name():
    """When a custom page model is in use, the page_ptr accessor might be
    different than the default 'page_ptr'."""
    if WAGTAIL_VERSION >= (8, 0):
        import swapper

        page_model_name = swapper.get_model_name("wagtailcore", "Page")
        parent_rel_name = f"{page_model_name.lower()}_ptr".split(".")[-1]
        return parent_rel_name
    return "page_ptr"


def make_test_page(parent, cls=None, **kwargs):
    cls = cls or TestPage
    kwargs.setdefault("title", "Test page")
    return parent.add_child(instance=cls(**kwargs))
