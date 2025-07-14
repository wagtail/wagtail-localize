from unittest.mock import patch

from django.contrib.admin.utils import quote
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.models import Locale, Page, PageViewRestriction
from wagtail.test.utils import WagtailTestUtils

from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.test.models import (
    NonTranslatableSnippet,
    TestPage,
    TestSnippet,
    TestWithTranslationModeDisabledPage,
    TestWithTranslationModeEnabledPage,
)

from .utils import assert_permission_denied, make_test_page


def strip_user_perms():
    """
    Removes user permissions so they can still access admin and edit pages but can't submit anything for translation.
    """
    editors_group = Group.objects.get(name="Editors")
    editors_group.permissions.filter(codename="submit_translation").delete()

    for permission in Permission.objects.filter(
        content_type=ContentType.objects.get_for_model(TestSnippet)
    ):
        editors_group.permissions.add(permission)

    for permission in Permission.objects.filter(
        content_type=ContentType.objects.get_for_model(NonTranslatableSnippet)
    ):
        editors_group.permissions.add(permission)

    user = get_user_model().objects.get()
    user.is_superuser = False
    user.groups.add(editors_group)
    user.save()


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
class TestTranslatePageListingButton(WagtailTestUtils, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.en_locale = Locale.objects.get()
        cls.fr_locale = Locale.objects.create(language_code="fr")
        cls.de_locale = Locale.objects.create(language_code="de")

        cls.en_homepage = Page.objects.get(depth=2)
        cls.fr_homepage = cls.en_homepage.copy_for_translation(cls.fr_locale)
        cls.de_homepage = cls.en_homepage.copy_for_translation(cls.de_locale)

        cls.en_blog_index = make_test_page(cls.en_homepage, title="Blog", slug="blog")

    def setUp(self):
        self.login()

    def _test_submit_for_translation_more_action(
        self, parent_page_id, expected_page_id
    ):
        response = self.client.get(
            reverse("wagtailadmin_explore", args=[parent_page_id])
        )

        suffix = ' class=""' if WAGTAIL_VERSION >= (7, 1) else ""

        self.assertContains(
            response,
            (
                f'<a href="/admin/localize/submit/page/{expected_page_id}/"{suffix}>'
                '<svg class="icon icon-wagtail-localize-language icon" aria-hidden="true">'
                '<use href="#icon-wagtail-localize-language"></use></svg>'
                "Translate this page"
                "</a>"
            ),
            html=True,
        )

        return response

    def test_submit_translation_link(self):
        self._test_submit_for_translation_more_action(
            self.en_homepage.pk, self.en_blog_index.pk
        )

    def test_submit_translation_shows_parent_id_for_alias_pages(self):
        alias_page = self.en_blog_index.create_alias(
            parent=self.fr_homepage,
            update_slug="the-page-alias",
        )
        response = self._test_submit_for_translation_more_action(
            self.fr_homepage.pk, self.en_blog_index.pk
        )

        self.assertNotContains(
            response, f"/admin/localize/submit/page/{alias_page.pk}/"
        )

    def test_hides_if_page_already_translated(self):
        self.en_blog_index.copy_for_translation(self.fr_locale)
        self.en_blog_index.copy_for_translation(self.de_locale)

        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertNotContains(response, "Translate this page")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertNotContains(response, "Translate this page")


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
class TestSubmitPageTranslation(WagtailTestUtils, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.en_locale = Locale.objects.get()
        cls.fr_locale = Locale.objects.create(language_code="fr")
        cls.de_locale = Locale.objects.create(language_code="de")

        cls.en_homepage = Page.objects.get(depth=2)
        cls.fr_homepage = cls.en_homepage.copy_for_translation(cls.fr_locale)
        cls.de_homepage = cls.en_homepage.copy_for_translation(cls.de_locale)

        cls.en_blog_index = make_test_page(cls.en_homepage, title="Blog", slug="blog")
        cls.en_blog_post = make_test_page(
            cls.en_blog_index, title="Blog post", slug="blog-post"
        )
        cls.en_blog_post_child = make_test_page(
            cls.en_blog_post, title="A deep page", slug="deep-page"
        )

    def setUp(self):
        self.login()

    def test_get_submit_page_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset),
            [self.de_locale, self.fr_locale],
        )

        # More than one locale so show "Select all"
        self.assertFalse(response.context["form"]["select_all"].field.widget.is_hidden)

        # Page has children so show "Include subtree"
        self.assertFalse(
            response.context["form"]["include_subtree"].field.widget.is_hidden
        )

    def test_get_submit_page_translation_when_already_translated(self):
        # Locales that have been translated into shouldn't be included
        self.en_blog_index.copy_for_translation(self.de_locale)

        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset), [self.fr_locale]
        )

        # Since there is only one locale, the "Select All" checkbox should be hidden
        self.assertTrue(response.context["form"]["select_all"].field.widget.is_hidden)

    def test_get_submit_page_translation_on_page_without_children(self):
        # Hide "Include subtree" input if there are no children
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post_child.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        # Page doesn't have children so hide "Include subtree"
        self.assertTrue(
            response.context["form"]["include_subtree"].field.widget.is_hidden
        )

    def test_get_submit_page_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post_child.id],
            )
        )

        assert_permission_denied(self, response)

    def test_get_submit_page_translation_on_root_page(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[1],
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation(self, _mock_on_commit):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

    @override_settings(WAGTAILLOCALIZE_SYNC_LIVE_STATUS_ON_TRANSLATE=False)
    def test_post_submit_page_translation_draft(self):
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertFalse(translated_page.live)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_submits_linked_snippets(
        self, _mock_on_commit
    ):
        self.en_blog_index.test_snippet = TestSnippet.objects.create(
            field="My test snippet"
        )
        self.en_blog_index.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        page_translation = Translation.objects.get(
            source__specific_content_type=ContentType.objects.get_for_model(TestPage)
        )
        self.assertEqual(page_translation.source.locale, self.en_locale)
        self.assertEqual(page_translation.target_locale, self.fr_locale)
        self.assertTrue(page_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        snippet_translation = Translation.objects.get(
            source__specific_content_type=ContentType.objects.get_for_model(TestSnippet)
        )
        self.assertEqual(snippet_translation.source.locale, self.en_locale)
        self.assertEqual(snippet_translation.target_locale, self.fr_locale)
        self.assertTrue(snippet_translation.created_at)

        # The translated snippet should've been created
        self.assertTrue(self.en_blog_index.test_snippet.has_translation(self.fr_locale))

    def test_post_submit_page_translation_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # Check French translation
        fr_translation = Translation.objects.get(target_locale=self.fr_locale)
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # Check German translation
        de_translation = Translation.objects.get(target_locale=self.de_locale)
        self.assertEqual(de_translation.source.locale, self.en_locale)
        self.assertTrue(de_translation.created_at)

    def test_post_submit_page_translation_including_subtree(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id], "include_subtree": "on"},
        )

        translated_page = self.en_blog_index.get_translation(self.fr_locale)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        # Check multiple translations were created
        self.assertEqual(Translation.objects.count(), 3)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_with_untranslated_parent(
        self, _mock_on_commit
    ):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        # One translation should be created
        fr_translation = Translation.objects.get()
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertEqual(fr_translation.target_locale, self.fr_locale)
        self.assertTrue(fr_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_post.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        # The parent should've been created as an alias page
        translated_parent_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_parent_page.live)
        self.assertEqual(translated_parent_page.alias_of, self.en_blog_index.page_ptr)

        # Just check the translation was created under its parent
        self.assertEqual(translated_page.get_parent(), translated_parent_page.page_ptr)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_with_untranslated_grandparent(
        self, _mock_on_commit
    ):
        # This is the same as the previous test, except it's done with a new locale so the homepage doesn't exist yet.
        # This should create a translation request that contains the homepage, blog index and the blog post that was requested.
        es_locale = Locale.objects.create(language_code="es")

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post.id],
            ),
            {"locales": [es_locale.id]},
        )

        # One translation should be created
        fr_translation = Translation.objects.get()
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertEqual(fr_translation.target_locale, es_locale)
        self.assertTrue(fr_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_post.get_translation(es_locale)
        self.assertTrue(translated_page.live)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        # The parent should've been created as an alias page
        translated_parent_page = self.en_blog_index.get_translation(es_locale)
        self.assertTrue(translated_parent_page.live)
        self.assertEqual(translated_parent_page.alias_of, self.en_blog_index.page_ptr)

        # The grandparent should've been created as an alias page
        translated_grandparent_page = self.en_homepage.get_translation(es_locale)
        self.assertTrue(translated_grandparent_page.live)
        self.assertEqual(translated_grandparent_page.alias_of, self.en_homepage)

        # Just check the translations were created in the right place
        self.assertEqual(translated_page.get_parent(), translated_parent_page.page_ptr)
        self.assertEqual(
            translated_parent_page.get_parent(), translated_grandparent_page
        )
        self.assertEqual(
            translated_grandparent_page.get_parent(), Page.objects.get(depth=1)
        )

    def test_post_submit_page_translation_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post.id],
            ),
            {"locales": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Translation.objects.exists())
        form = response.context["form"]
        self.assertIn("locales", form.errors)
        self.assertEqual(form.errors["locales"], ["This field is required."])

    def test_post_submit_page_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        assert_permission_denied(self, response)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_reactivates_deleted_translation(
        self, _mock_on_commit
    ):
        # Create a disabled translation record
        # This simulates the case where the page was previously translated into that locale but later deleted
        source, created = TranslationSource.get_or_create_from_instance(
            self.en_blog_index
        )
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
            enabled=False,
        )

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        # Check that the translation was reactivated
        # Note, .get() here tests that another translation record wasn't created
        translation = Translation.objects.get()
        self.assertEqual(translation.source, source)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.enabled)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_doesnt_reactivate_deactivated_translation(
        self, _mock_on_commit
    ):
        # Like the previous test, this creates a disabled translation record, but this
        # time, the translation has not been deleted. It should not reactivate in this case
        source, created = TranslationSource.get_or_create_from_instance(
            self.en_blog_index
        )
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )
        translation.save_target()

        translation.enabled = False
        translation.save(update_fields=["enabled"])

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        # Form error
        self.assertEqual(response.status_code, 200)

        # Note, .get() here tests that another translation record wasn't created
        translation = Translation.objects.get()
        self.assertFalse(translation.enabled)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

    @override_settings(WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE="simple")
    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_with_global_disabled_mode(
        self, _mock_on_commit
    ):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        translation = Translation.objects.get()
        self.assertFalse(translation.enabled)

    def test_post_submit_page_translation_with_disabled_mode_per_page_type(self):
        custom_page = make_test_page(
            self.en_homepage,
            cls=TestWithTranslationModeDisabledPage,
            title="Translation mode test",
            slug="translation-mode-test",
        )
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[custom_page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translated_page = custom_page.get_translation(self.fr_locale)
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        translation = Translation.objects.get()
        self.assertFalse(translation.enabled)

    @override_settings(WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE="simple")
    def test_post_submit_page_translation_with_global_mode_disabled_but_enabled_per_page_type(
        self,
    ):
        custom_page = make_test_page(
            self.en_homepage,
            cls=TestWithTranslationModeEnabledPage,
            title="Translation mode test",
            slug="translation-mode-test",
        )
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[custom_page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translated_page = custom_page.get_translation(self.fr_locale)
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )

        translation = Translation.objects.get()
        self.assertTrue(translation.enabled)

    @patch.object(transaction, "on_commit", side_effect=lambda func: func())
    def test_post_submit_page_translation_from_page_with_privacy_settings(
        self, _mock_on_commit
    ):
        view_restriction = PageViewRestriction.objects.create(
            restriction_type="login", page=self.en_blog_index
        )

        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        # The translated page should've been created and published, and have a view restriction
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)
        self.assertTrue(translated_page.view_restrictions.exists())
        self.assertTrue(
            translated_page.view_restrictions.first().pk, view_restriction.pk
        )

    def test_post_submit_page_translation_from_draft_source_still_draft(self):
        custom_page = make_test_page(
            self.en_homepage,
            cls=TestPage,
            title="Translation draft state test",
            slug="translation-draft-state-test",
            live=False,
        )
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[custom_page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translated_page = Translation.objects.get().get_target_instance()

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[translated_page.id])
        )
        self.assertFalse(translated_page.live)


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
class TestTranslateSnippetListingButton(WagtailTestUtils, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.en_locale = Locale.objects.get()
        cls.fr_locale = Locale.objects.create(language_code="fr")
        cls.de_locale = Locale.objects.create(language_code="de")

        cls.en_snippet = TestSnippet.objects.create(field="Test snippet")
        cls.fr_snippet = cls.en_snippet.copy_for_translation(cls.fr_locale)
        cls.fr_snippet.save()

        cls.not_translatable_snippet = NonTranslatableSnippet.objects.create()

    def setUp(self):
        self.login()

    def test(self):
        response = self.client.get(
            reverse("wagtailsnippets_wagtail_localize_test_testsnippet:list")
        )

        self.assertContains(
            response,
            (
                f'<a href="/admin/localize/submit/snippet/wagtail_localize_test/testsnippet/{self.en_snippet.id}/" '
                f'aria-label="Translate &#x27;{self.en_snippet}&#x27;">'
                f'<svg class="icon icon-wagtail-localize-language icon" aria-hidden="true"><use href="#icon-wagtail-localize-language"></use></svg>'
                f"Translate</a>"
            ),
            html=True,
        )

    def test_hides_if_snippet_already_translated(self):
        de_snippet = self.en_snippet.copy_for_translation(self.de_locale)
        de_snippet.save()

        response = self.client.get(
            reverse("wagtailsnippets_wagtail_localize_test_testsnippet:list")
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_snippet_isnt_translatable(self):
        self.en_snippet.copy_for_translation(self.de_locale)

        response = self.client.get(
            reverse("wagtailsnippets_wagtail_localize_test_nontranslatablesnippet:list")
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse("wagtailsnippets_wagtail_localize_test_testsnippet:list")
        )

        self.assertNotContains(response, "Translate")


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
class TestSubmitSnippetTranslation(WagtailTestUtils, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.en_locale = Locale.objects.get()
        cls.fr_locale = Locale.objects.create(language_code="fr")
        cls.de_locale = Locale.objects.create(language_code="de")

        cls.en_snippet = TestSnippet.objects.create(field="Test snippet")

        cls.not_translatable_snippet = NonTranslatableSnippet.objects.create()

    def setUp(self):
        self.login()

    def test_get_submit_snippet_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset),
            [self.de_locale, self.fr_locale],
        )

        # More than one locale so show "Select all"
        self.assertFalse(response.context["form"]["select_all"].field.widget.is_hidden)

        # Snippets can't have children so hide include_subtree
        self.assertTrue(
            response.context["form"]["include_subtree"].field.widget.is_hidden
        )

    def test_get_submit_snippet_translation_when_not_snippet(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtailcore", "page", 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_when_invalid_model(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtailcore", "foo", 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_when_not_translatable(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=[
                    "wagtail_localize_test",
                    "nontranslatablesnippet",
                    self.not_translatable_snippet.id,
                ],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            )
        )

        assert_permission_denied(self, response)

    def test_get_submit_snippet_translation_when_already_translated(self):
        # Locales that have been translated into shouldn't be included
        translation = self.en_snippet.copy_for_translation(self.de_locale)
        translation.save()

        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset), [self.fr_locale]
        )

        # Since there is only one locale, the "Select All" checkbox should be hidden
        self.assertTrue(response.context["form"]["select_all"].field.widget.is_hidden)

    def test_post_submit_snippet_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated snippet should've been created
        translated_snippet = self.en_snippet.get_translation(self.fr_locale)
        self.assertEqual(translated_snippet.field, "Test snippet")

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{translated_snippet._meta.app_label}_{translated_snippet._meta.model_name}:edit",
                args=[quote(translated_snippet.pk)],
            ),
        )

    @override_settings(WAGTAILLOCALIZE_SYNC_LIVE_STATUS_ON_TRANSLATE=False)
    def test_post_submit_snippet_translation_draft(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated snippet should've been created
        translated_snippet = self.en_snippet.get_translation(self.fr_locale)
        self.assertEqual(translated_snippet.field, "Test snippet")
        self.assertFalse(translated_snippet.live)

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{translated_snippet._meta.app_label}_{translated_snippet._meta.model_name}:edit",
                args=[quote(translated_snippet.pk)],
            ),
        )

    def test_post_submit_snippet_translation_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id]},
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.en_snippet._meta.app_label}_{self.en_snippet._meta.model_name}:edit",
                args=[quote(self.en_snippet.pk)],
            ),
        )

        # Check French translation
        fr_translation = Translation.objects.get(target_locale=self.fr_locale)
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # Check German translation
        de_translation = Translation.objects.get(target_locale=self.de_locale)
        self.assertEqual(de_translation.source.locale, self.en_locale)
        self.assertTrue(de_translation.created_at)

    def test_post_submit_snippet_translation_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
            {"locales": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Translation.objects.exists())
        form = response.context["form"]
        self.assertIn("locales", form.errors)
        self.assertEqual(form.errors["locales"], ["This field is required."])

    def test_post_submit_snippet_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        assert_permission_denied(self, response)
