from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page, Locale
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.test.models import TestPage

from wagtail_localize.git.models import Resource


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    source, created = TranslationSource.get_or_create_from_instance(page)
    return page, source


class TestDashboardView(WagtailTestUtils, TestCase):
    def setUp(self):
        self.locale_en = Locale.objects.get(language_code="en")
        self.locale_fr = Locale.objects.create(language_code="fr")

        self.page, self.source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some test translatable content",
        )
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.locale_fr,
        )
        self.resource = Resource.get_for_object(self.source.object)

        self.login()
        self.user = get_user_model().objects.get()

    def test_get_dashboard_view(self):
        response = self.client.get(reverse('wagtail_localize_git:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_get_dashboard_without_perms(self):
        # Convert the user into a moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        response = self.client.get(reverse('wagtail_localize_git:dashboard'))
        self.assertEqual(response.status_code, 302)


@mock.patch('wagtail_localize.git.sync.SyncManager.trigger')
class TestForceSyncView(WagtailTestUtils, TestCase):
    def setUp(self):
        self.locale_en = Locale.objects.get(language_code="en")
        self.locale_fr = Locale.objects.create(language_code="fr")

        self.page, self.source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some test translatable content",
        )
        self.translation = Translation.objects.create(
            source=self.source,
            target_locale=self.locale_fr,
        )
        self.resource = Resource.get_for_object(self.source.object)

        self.login()
        self.user = get_user_model().objects.get()

    def test_post_force_sync(self, trigger):
        response = self.client.post(reverse('wagtail_localize_git:force_sync'))
        self.assertRedirects(response, reverse('wagtail_localize_git:dashboard'))

        trigger.assert_called()

    def test_post_force_sync_without_perms(self, trigger):
        # Convert the user into a moderator
        self.moderators_group = Group.objects.get(name="Moderators")
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        response = self.client.post(reverse('wagtail_localize_git:force_sync'))
        self.assertEqual(response.status_code, 302)

        trigger.assert_not_called()
