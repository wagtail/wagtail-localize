from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import Locale
from wagtail_localize.test.models import TestPage, TestHomePage
from wagtail_localize.workflow.models import TranslationRequest


def make_test_page(parent, cls=None, **kwargs):
    cls = cls or TestPage
    kwargs.setdefault("title", "Test page")
    return parent.add_child(instance=cls(**kwargs))


class TestCreateTranslationRequest(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_homepage = TestHomePage.objects.get()
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.en_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = make_test_page(self.en_homepage, title="Blog", slug="blog")
        self.en_blog_post = make_test_page(
            self.en_blog_index, title="Blog post", slug="blog-post"
        )
        self.en_blog_post_child = make_test_page(
            self.en_blog_post, title="A deep page", slug="deep-page"
        )
        self.not_translatable_blog_post = make_test_page(
            self.en_blog_index,
            title="Not traslatable blog post",
            slug="not-translatable-blog-post",
            cls=Page,
        )

    def test_get_create_translation_request(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_index.id],
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_post_create_translation_request(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id],},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        translation_request = TranslationRequest.objects.get()
        self.assertEqual(translation_request.source_locale, self.en_locale)
        self.assertEqual(translation_request.target_locale, self.fr_locale)
        self.assertEqual(translation_request.target_root, self.fr_homepage.page_ptr)
        self.assertTrue(translation_request.created_at)
        self.assertEqual(translation_request.created_by.username, "test@email.com")

        translation_request_page = translation_request.pages.get()
        self.assertEqual(
            translation_request_page.source_revision,
            self.en_blog_index.get_latest_revision(),
        )
        self.assertIsNone(translation_request_page.parent)
        self.assertFalse(translation_request_page.is_completed)
        self.assertIsNone(translation_request_page.completed_revision)

    def test_post_create_translation_request_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id],},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        # Check French translation request
        fr_translation_request = TranslationRequest.objects.get(
            target_locale=self.fr_locale
        )
        self.assertEqual(fr_translation_request.source_locale, self.en_locale)
        self.assertEqual(fr_translation_request.target_root, self.fr_homepage.page_ptr)
        self.assertTrue(fr_translation_request.created_at)
        self.assertEqual(fr_translation_request.created_by.username, "test@email.com")

        fr_translation_request_page = fr_translation_request.pages.get()
        self.assertEqual(
            fr_translation_request_page.source_revision,
            self.en_blog_index.get_latest_revision(),
        )
        self.assertIsNone(fr_translation_request_page.parent)
        self.assertFalse(fr_translation_request_page.is_completed)
        self.assertIsNone(fr_translation_request_page.completed_revision)

        # Check German translation request
        de_translation_request = TranslationRequest.objects.get(
            target_locale=self.de_locale
        )
        self.assertEqual(de_translation_request.source_locale, self.en_locale)
        self.assertEqual(de_translation_request.target_root, self.de_homepage.page_ptr)
        self.assertTrue(de_translation_request.created_at)
        self.assertEqual(de_translation_request.created_by.username, "test@email.com")

        de_translation_request_page = de_translation_request.pages.get()
        self.assertEqual(
            de_translation_request_page.source_revision,
            self.en_blog_index.get_latest_revision(),
        )
        self.assertIsNone(de_translation_request_page.parent)
        self.assertFalse(de_translation_request_page.is_completed)
        self.assertIsNone(de_translation_request_page.completed_revision)

    def test_post_create_translation_request_including_subtree(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id], "include_subtree": "on",},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        translation_request = TranslationRequest.objects.get()
        self.assertEqual(translation_request.source_locale, self.en_locale)
        self.assertEqual(translation_request.target_locale, self.fr_locale)
        self.assertEqual(translation_request.target_root, self.fr_homepage.page_ptr)
        self.assertTrue(translation_request.created_at)
        self.assertEqual(translation_request.created_by.username, "test@email.com")

        # Check translation request page for root (blog index)
        translation_request_root_page = translation_request.pages.get(parent=None)
        self.assertEqual(
            translation_request_root_page.source_revision,
            self.en_blog_index.get_latest_revision(),
        )
        self.assertFalse(translation_request_root_page.is_completed)
        self.assertIsNone(translation_request_root_page.completed_revision)

        # Check translation request page for child (blog post)
        translation_request_child_page = translation_request.pages.get(
            parent=translation_request_root_page
        )
        self.assertEqual(
            translation_request_child_page.source_revision,
            self.en_blog_post.get_latest_revision(),
        )
        self.assertFalse(translation_request_child_page.is_completed)
        self.assertIsNone(translation_request_child_page.completed_revision)

        # Check translation request page for grandchild (blog post child)
        translation_request_grandchild_page = translation_request.pages.get(
            parent=translation_request_child_page
        )
        self.assertEqual(
            translation_request_grandchild_page.source_revision,
            self.en_blog_post_child.get_latest_revision(),
        )
        self.assertFalse(translation_request_grandchild_page.is_completed)
        self.assertIsNone(translation_request_grandchild_page.completed_revision)

    def test_post_create_translation_request_with_untranslated_parent(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_post.id],
            ),
            {"locales": [self.fr_locale.id],},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        translation_request = TranslationRequest.objects.get()
        self.assertEqual(translation_request.source_locale, self.en_locale)
        self.assertEqual(translation_request.target_locale, self.fr_locale)
        self.assertEqual(translation_request.target_root, self.fr_homepage.page_ptr)
        self.assertTrue(translation_request.created_at)
        self.assertEqual(translation_request.created_by.username, "test@email.com")

        # Check translation request page for root (blog index)
        # This is added automatically. The blog post was requested but this is required in order for there
        # to be somewhere for the translated blog post to exist in the destination tree
        translation_request_root_page = translation_request.pages.get(parent=None)
        self.assertEqual(
            translation_request_root_page.source_revision,
            self.en_blog_index.get_latest_revision(),
        )
        self.assertFalse(translation_request_root_page.is_completed)
        self.assertIsNone(translation_request_root_page.completed_revision)

        # Check translation request page for child (blog post)
        translation_request_child_page = translation_request.pages.get(
            parent=translation_request_root_page
        )
        self.assertEqual(
            translation_request_child_page.source_revision,
            self.en_blog_post.get_latest_revision(),
        )
        self.assertFalse(translation_request_child_page.is_completed)
        self.assertIsNone(translation_request_child_page.completed_revision)

    def test_post_create_translation_request_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.en_blog_post.id],
            ),
            {"locales": [],},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TranslationRequest.objects.exists())
        self.assertFormError(response, "form", "locales", ["This field is required."])

    def test_post_create_translation_request_with_untranslatable_page(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_workflow:create_translation_request",
                args=[self.not_translatable_blog_post.id],
            ),
            {"locales": [self.fr_locale.id],},
            follow=True,
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(TranslationRequest.objects.exists())
