from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import Locale
from wagtail_localize.test.models import TestPage, TestHomePage
from wagtail_localize.translation.models import Translation, TranslationSource


def make_test_page(parent, cls=None, **kwargs):
    cls = cls or TestPage
    kwargs.setdefault("title", "Test page")
    return parent.add_child(instance=cls(**kwargs))


def create_test_locales(test):
    test.en_locale = Locale.objects.get()
    test.fr_locale = Locale.objects.create(language_code="fr")
    test.de_locale = Locale.objects.create(language_code="de")


def create_test_pages(test):
    test.en_homepage = TestHomePage.objects.get()
    test.fr_homepage = test.en_homepage.copy_for_translation(test.fr_locale)
    test.de_homepage = test.en_homepage.copy_for_translation(test.de_locale)

    test.en_blog_index = make_test_page(test.en_homepage, title="Blog", slug="blog")
    test.en_blog_post = make_test_page(
        test.en_blog_index, title="Blog post", slug="blog-post"
    )
    test.en_blog_post_child = make_test_page(
        test.en_blog_post, title="A deep page", slug="deep-page"
    )
    test.not_translatable_blog_post = make_test_page(
        test.en_blog_index,
        title="Not traslatable blog post",
        slug="not-translatable-blog-post",
        cls=Page,
    )


class TestCreateTranslationRequest(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        create_test_locales(self)
        create_test_pages(self)

    def test_get_create_translation_request(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_index.id],
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_post_create_translation_request(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # TODO
        # translation_request_page = translation.pages.get()
        # self.assertEqual(
        #     translation_request_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertIsNone(translation_request_page.parent)
        # self.assertFalse(translation_request_page.is_completed)
        # self.assertIsNone(translation_request_page.completed_revision)

    def test_post_create_translation_request_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_homepage.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[1])
        )

        # Check French translation request
        fr_translation = Translation.objects.get(
            target_locale=self.fr_locale
        )
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # TODO
        # fr_translation_page = fr_translation.pages.get()
        # self.assertEqual(
        #     fr_translation_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertIsNone(fr_translation_page.parent)
        # self.assertFalse(fr_translation_page.is_completed)
        # self.assertIsNone(fr_translation_page.completed_revision)

        # Check German translation request
        de_translation = Translation.objects.get(
            target_locale=self.de_locale
        )
        self.assertEqual(de_translation.source.locale, self.en_locale)
        self.assertTrue(de_translation.created_at)

        # TODO
        # de_translation_request_page = de_translation.pages.get()
        # self.assertEqual(
        #     de_translation_request_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertIsNone(de_translation_request_page.parent)
        # self.assertFalse(de_translation_request_page.is_completed)
        # self.assertIsNone(de_translation_request_page.completed_revision)

    def test_post_create_translation_request_including_subtree(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id], "include_subtree": "on"},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        # TODO
        # translation = Translation.objects.get()
        # self.assertEqual(translation.source.locale, self.en_locale)
        # self.assertEqual(translation.target_locale, self.fr_locale)
        # self.assertTrue(translation.created_at)

        # TODO
        # Check translation request page for root (blog index)
        # translation_request_root_page = translation.pages.get(parent=None)
        # self.assertEqual(
        #     translation_request_root_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_root_page.is_completed)
        # self.assertIsNone(translation_request_root_page.completed_revision)

        # # Check translation request page for child (blog post)
        # translation_request_child_page = translation.pages.get(
        #     parent=translation_request_root_page
        # )
        # self.assertEqual(
        #     translation_request_child_page.source_revision,
        #     self.en_blog_post.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_child_page.is_completed)
        # self.assertIsNone(translation_request_child_page.completed_revision)

        # # Check translation request page for grandchild (blog post child)
        # translation_request_grandchild_page = translation.pages.get(
        #     parent=translation_request_child_page
        # )
        # self.assertEqual(
        #     translation_request_grandchild_page.source_revision,
        #     self.en_blog_post_child.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_grandchild_page.is_completed)
        # self.assertIsNone(translation_request_grandchild_page.completed_revision)

    def test_post_create_translation_request_with_untranslated_parent(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_post.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # TODO
        # translation = Translation.objects.get()
        # self.assertEqual(translation.source.locale, self.en_locale)
        # self.assertEqual(translation.target_locale, self.fr_locale)
        # self.assertTrue(translation.created_at)

        # TODO
        # Check translation request page for root (blog index)
        # This is added automatically. The blog post was requested but this is required in order for there
        # to be somewhere for the translated blog post to exist in the destination tree
        # translation_request_root_page = translation.pages.get(parent=None)
        # self.assertEqual(
        #     translation_request_root_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_root_page.is_completed)
        # self.assertIsNone(translation_request_root_page.completed_revision)

        # # Check translation request page for child (blog post)
        # translation_request_child_page = translation.pages.get(
        #     parent=translation_request_root_page
        # )
        # self.assertEqual(
        #     translation_request_child_page.source_revision,
        #     self.en_blog_post.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_child_page.is_completed)
        # self.assertIsNone(translation_request_child_page.completed_revision)

    def test_post_create_translation_request_with_untranslated_grandparent(self):
        # This is the same as the previous test, except it's done with a new locale so the homepage doesn't exist yet.
        # This should create a translation request that contains the homepage, blog index and the blog post that was requested.
        es_locale = Locale.objects.create(language_code="es")

        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_post.id],
            ),
            {"locales": [es_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # TODO
        # translation = Translation.objects.get()
        # self.assertEqual(translation.source.locale, self.en_locale)
        # self.assertEqual(translation.target_locale, es_locale)
        # self.assertTrue(translation.created_at)

        # TODO
        # Check translation request page for root (homepage)
        # This is added automatically. The blog post was requested but this is required in order for there
        # to be somewhere for the translated blog post to exist in the destination tree
        # translation_request_root_page = translation.pages.get(parent=None)
        # self.assertEqual(
        #     translation_request_root_page.source_revision,
        #     self.en_homepage.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_root_page.is_completed)
        # self.assertIsNone(translation_request_root_page.completed_revision)

        # # Check translation request page for child (blog index)
        # translation_request_child_page = translation.pages.get(
        #     parent=translation_request_root_page
        # )
        # self.assertEqual(
        #     translation_request_child_page.source_revision,
        #     self.en_blog_index.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_child_page.is_completed)
        # self.assertIsNone(translation_request_child_page.completed_revision)

        # # Check translation request page for grandchild (blog)
        # translation_request_grandchild_page = translation.pages.get(
        #     parent=translation_request_child_page
        # )
        # self.assertEqual(
        #     translation_request_grandchild_page.source_revision,
        #     self.en_blog_post.get_latest_revision(),
        # )
        # self.assertFalse(translation_request_grandchild_page.is_completed)
        # self.assertIsNone(translation_request_grandchild_page.completed_revision)

    def test_post_create_translation_request_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.en_blog_post.id],
            ),
            {"locales": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Translation.objects.exists())
        self.assertFormError(response, "form", "locales", ["This field is required."])

    def test_post_create_translation_request_with_untranslatable_page(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_translation:create_translation_request",
                args=[self.not_translatable_blog_post.id],
            ),
            {"locales": [self.fr_locale.id]},
            follow=True,
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Translation.objects.exists())


def get_or_create_translation(instance, target_locale):
    source, created = TranslationSource.from_instance(instance)

    return Translation.objects.get_or_create(
        object=source.object,
        target_locale=target_locale,
        source=source,
    )


def create_test_translations(test):
    test.blog_index_translation = get_or_create_translation(test.en_blog_index, test.fr_locale)[0]
    test.blog_post_translation = get_or_create_translation(test.en_blog_post, test.fr_locale)[0]


class TestTranslationListing(TestCase, WagtailTestUtils):
    def setUp(self):
        self.user = self.create_test_user()
        self.login(self.user)

        create_test_locales(self)
        create_test_pages(self)
        create_test_translations(self)

    def test_get(self):
        response = self.client.get(reverse("wagtail_localize_translation_management:list"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            reverse(
                "wagtail_localize_translation_management:detail",
                args=[self.blog_index_translation.id],
            ),
        )


class TestTranslationDetail(TestCase, WagtailTestUtils):
    def setUp(self):
        self.user = self.create_test_user()
        self.login(self.user)

        create_test_locales(self)
        create_test_pages(self)
        create_test_translations(self)

    def test_get(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_translation_management:detail",
                args=[self.blog_index_translation.id],
            )
        )

        self.assertEqual(response.status_code, 200)
