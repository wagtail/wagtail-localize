from django.test import TestCase
from wagtail.core import hooks
from wagtail.core.models import Locale, Page
from wagtail.tests.utils import WagtailTestUtils


class TestConstructSyncedPageTreeListHook(WagtailTestUtils, TestCase):
    def setUp(self):
        self.en_locale = Locale.objects.first()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_homepage = Page.objects.get(depth=2)
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.en_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = Page(title="Blog", slug="blog")
        self.en_homepage.add_child(instance=self.en_blog_index)

        self.en_blog_post = Page(title="Blog post", slug="blog-post")
        self.en_blog_index.add_child(instance=self.en_blog_post)

    def unpublish_hook(self, pages, action):
        assert action == "unpublish"
        assert isinstance(pages, list)

    def missing_hook_action(self, pages, action):
        assert action == ""
        assert isinstance(pages, list)

    def test_double_registered_hook(self):
        # We should have two implementations of `construct_synced_page_tree_list`
        # One in simple_translation.wagtail_hooks and the other will be
        # registered as a temporary hook.
        with hooks.register_temporarily(
            "construct_synced_page_tree_list", self.unpublish_hook
        ):
            defined_hooks = hooks.get_hooks("construct_synced_page_tree_list")
            self.assertEqual(len(defined_hooks), 2)

    def test_page_tree_sync_on(self):
        with hooks.register_temporarily(
            "construct_synced_page_tree_list", self.unpublish_hook
        ):
            for fn in hooks.get_hooks("construct_synced_page_tree_list"):
                response = fn([self.en_homepage], "unpublish")
                if response:
                    assert isinstance(response, dict)
                    assert len(response.items()) == 1

    def test_page_tree_sync_off(self):
        with hooks.register_temporarily(
            "construct_synced_page_tree_list", self.unpublish_hook
        ):
            for fn in hooks.get_hooks("construct_synced_page_tree_list"):
                response = fn([self.en_homepage], "unpublish")
                assert response is None

    def test_missing_hook_action(self):
        with hooks.register_temporarily(
            "construct_synced_page_tree_list", self.missing_hook_action
        ):
            for fn in hooks.get_hooks("construct_synced_page_tree_list"):
                response = fn([self.en_homepage], "")
                if response is not None:
                    assert isinstance(response, dict)
