from django.contrib import messages
from django.urls import reverse


def assert_permission_denied(self, response):
    # Checks for Wagtail's permission denied response
    self.assertRedirects(response, reverse('wagtailadmin_home'))

    raised_messages = [
        (message.level_tag, message.message)
        for message in messages.get_messages(response.wsgi_request)
    ]
    self.assertIn(('error', 'Sorry, you do not have permission to access this area.\n\n\n\n\n'), raised_messages)
