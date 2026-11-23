from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from tests.testapp.models import TestPage


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


def make_user_translate_but_not_edit():
    """
    Removes user permissions so they can still access admin and submit translations
    but can't edit pages or snippets.
    """
    user = get_user_model().objects.get()
    user.is_superuser = False
    user.user_permissions.add(
        Permission.objects.get(codename="access_admin"),
        Permission.objects.get(codename="submit_translation"),
    )
    user.save()
