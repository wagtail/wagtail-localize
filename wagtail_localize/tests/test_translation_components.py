from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.core.models import Locale, Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.test.models import (
    CustomButSimpleTranslationData,
    CustomTranslationData,
)
from wagtail_localize.views.submit_translations import TranslationComponentManager

from .utils import make_test_page


@override_settings(
    LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
)
class TestSubmitPageTranslationWithComponents(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_homepage = Page.objects.get(depth=2)
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.en_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = make_test_page(self.en_homepage, title="Blog", slug="blog")
        self.en_blog_post = make_test_page(
            self.en_blog_index, title="Blog post", slug="blog-post"
        )
        self.en_blog_post_child = make_test_page(
            self.en_blog_post, title="A deep page", slug="deep-page"
        )

    def test_get_submit_page_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertIsInstance(
            response.context["components"], TranslationComponentManager
        )
        self.assertContains(response, "Custom translation view component")
        self.assertContains(response, "Custom text field")

    def test_post_submit_page_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {
                "locales": [self.fr_locale.id],
                "component-wagtail_localize_test_customtranslationdata-enabled": True,
            },
        )

        self.assertContains(
            response, "component-form__fieldname-custom_text_field error"
        )
        self.assertContains(response, "This field is required")

        self.assertEqual(CustomTranslationData.objects.count(), 0)

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {
                "locales": [self.fr_locale.id],
                "component-wagtail_localize_test_customtranslationdata-enabled": True,
                "component-wagtail_localize_test_customtranslationdata-custom_text_field": "foo",
            },
        )

        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        self.assertEqual(CustomTranslationData.objects.count(), 1)

        custom_data = CustomTranslationData.objects.last()
        self.assertEqual(custom_data.custom_text_field, "foo")

    def test_post_submit_page_translation_with_include_children_creates_corresponding_component_instances(
        self,
    ):
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {
                "locales": [self.fr_locale.id],
                "include_subtree": "true",
                "component-wagtail_localize_test_customtranslationdata-enabled": True,
                "component-wagtail_localize_test_customtranslationdata-custom_text_field": "foo",
                "component-wagtail_localize_test_custombutsimpletranslationdata-enabled": True,
                "component-wagtail_localize_test_custombutsimpletranslationdata-notes": "Here be dragons",
            },
        )
        self.assertEqual(
            CustomTranslationData.objects.count(), 3
        )  # 1 for each translation source
        # just one, as it doesn't have a `get_or_create_from_source_and_translation_data` method
        self.assertEqual(CustomButSimpleTranslationData.objects.count(), 1)
