from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Locale, Page
from wagtail.test.utils import WagtailTestUtils

from wagtail_localize.models import (
    String,
    StringTranslation,
    Translation,
    TranslationContext,
    TranslationSource,
)
from wagtail_localize.test.models import TestSnippet

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
class TestTranslationReport(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_snippet = TestSnippet.objects.create(field="Test snippet")

        self.en_homepage = Page.objects.get(depth=2)
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.fr_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = make_test_page(self.en_homepage, title="Blog", slug="blog")
        self.en_blog_post = make_test_page(
            self.en_blog_index,
            title="Blog post",
            slug="blog-post",
            test_charfield="Test content",
        )

        self.snippet_translation = Translation.objects.create(
            source=TranslationSource.get_or_create_from_instance(self.en_snippet)[0],
            target_locale=self.fr_locale,
        )

        self.homepage_translation = Translation.objects.create(
            source=TranslationSource.get_or_create_from_instance(self.en_homepage)[0],
            target_locale=self.fr_locale,
        )

        self.de_homepage_translation = Translation.objects.create(
            source=TranslationSource.get_or_create_from_instance(self.fr_homepage)[0],
            target_locale=self.de_locale,
        )

        self.blog_index_translation = Translation.objects.create(
            source=TranslationSource.get_or_create_from_instance(self.en_blog_index)[0],
            target_locale=self.fr_locale,
        )

        self.blog_post_translation = Translation.objects.create(
            source=TranslationSource.get_or_create_from_instance(self.en_blog_post)[0],
            target_locale=self.fr_locale,
        )
        self.test_charfield_context = TranslationContext.objects.get(
            path="test_charfield"
        )
        self.test_content_string = String.objects.get(data="Test content")

    def test_get_empty_report(self):
        Translation.objects.all().delete()

        response = self.client.get(reverse("wagtail_localize:translations_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No translations found.")

    def test_get_report(self):
        response = self.client.get(reverse("wagtail_localize:translations_report"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "No translations found.")

        self.assertIn(self.snippet_translation, response.context["object_list"])
        self.assertIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        self.assertIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_content_type(self):
        snippet_content_type = ContentType.objects.get_for_model(TestSnippet)
        response = self.client.get(
            reverse("wagtail_localize:translations_report")
            + "?content_type="
            + str(snippet_content_type.id)
        )

        self.assertIn(self.snippet_translation, response.context["object_list"])
        self.assertNotIn(self.homepage_translation, response.context["object_list"])
        self.assertNotIn(self.blog_index_translation, response.context["object_list"])
        self.assertNotIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_base_content_type(self):
        snippet_content_type = ContentType.objects.get_for_model(Page)
        response = self.client.get(
            reverse("wagtail_localize:translations_report")
            + "?content_type="
            + str(snippet_content_type.id)
        )

        self.assertNotIn(self.snippet_translation, response.context["object_list"])
        self.assertIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        self.assertIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_source_title(self):
        response = self.client.get(
            reverse("wagtail_localize:translations_report") + "?source_title=Blog"
        )

        self.assertNotIn(self.snippet_translation, response.context["object_list"])
        self.assertNotIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        self.assertIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_source_locale(self):
        response = self.client.get(
            reverse("wagtail_localize:translations_report") + "?source_locale=fr"
        )

        self.assertNotIn(self.snippet_translation, response.context["object_list"])
        self.assertNotIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        self.assertNotIn(self.blog_index_translation, response.context["object_list"])
        self.assertNotIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_source_locale_all_options(self):
        response = self.client.get(
            reverse("wagtail_localize:translations_report") + "?source_locale=all"
        )

        self.assertIn(self.snippet_translation, response.context["object_list"])
        self.assertIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        self.assertIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_target_locale(self):
        response = self.client.get(
            reverse("wagtail_localize:translations_report") + "?target_locale=de"
        )

        self.assertNotIn(self.snippet_translation, response.context["object_list"])
        self.assertNotIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        self.assertNotIn(self.blog_index_translation, response.context["object_list"])
        self.assertNotIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_target_locale_all_options(self):
        response = self.client.get(
            reverse("wagtail_localize:translations_report") + "?target_locale=all"
        )

        self.assertIn(self.snippet_translation, response.context["object_list"])
        self.assertIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        self.assertIn(self.blog_post_translation, response.context["object_list"])

    def test_locale_filters_get_proper_choices(self):
        response = self.client.get(reverse("wagtail_localize:translations_report"))

        self.assertEqual(
            list(response.context["filters"].form.fields["source_locale"].choices),
            [
                ("all", "All"),
                ("en", "English"),
                ("fr", "French"),
                ("de", "German"),
                ("es", "Spanish"),
            ],
        )

        self.assertEqual(
            list(response.context["filters"].form.fields["target_locale"].choices),
            [
                ("all", "All"),
                ("en", "English"),
                ("fr", "French"),
                ("de", "German"),
                ("es", "Spanish"),
            ],
        )

    def test_filter_by_waiting_for_translation_true(self):
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )
        response = self.client.get(
            reverse("wagtail_localize:translations_report")
            + "?waiting_for_translation=true"
        )

        # These pages don't have any translations, so they should be listed
        self.assertIn(self.snippet_translation, response.context["object_list"])
        self.assertIn(self.homepage_translation, response.context["object_list"])
        self.assertIn(self.de_homepage_translation, response.context["object_list"])
        # Blog index page has no translatable strings, so should not be included
        self.assertNotIn(self.blog_index_translation, response.context["object_list"])
        # Translation is complete for this page, so should not be included
        self.assertNotIn(self.blog_post_translation, response.context["object_list"])

    def test_filter_by_waiting_for_translation_false(self):
        StringTranslation.objects.create(
            translation_of=self.test_content_string,
            context=self.test_charfield_context,
            locale=self.fr_locale,
            data="Contenu de test",
        )
        response = self.client.get(
            reverse("wagtail_localize:translations_report")
            + "?waiting_for_translation=false"
        )

        # These pages don't have any translations, so they should not be listed
        self.assertNotIn(self.snippet_translation, response.context["object_list"])
        self.assertNotIn(self.homepage_translation, response.context["object_list"])
        self.assertNotIn(self.de_homepage_translation, response.context["object_list"])
        # Blog index page has no translatable strings, so should be included
        self.assertIn(self.blog_index_translation, response.context["object_list"])
        # Translation is complete for this page, so should be included
        self.assertIn(self.blog_post_translation, response.context["object_list"])
