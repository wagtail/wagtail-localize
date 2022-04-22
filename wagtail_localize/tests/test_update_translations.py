from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.core.models import Locale, Page, PageViewRestriction
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import StringSegment, Translation, TranslationSource
from wagtail_localize.test.models import NonTranslatableSnippet, TestSnippet

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
class TestPageUpdateTranslationsListingButton(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_homepage = Page.objects.get(depth=2)
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.en_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = make_test_page(self.en_homepage, title="Blog", slug="blog")

        self.source, created = TranslationSource.get_or_create_from_instance(
            self.en_blog_index
        )
        self.translation = Translation.objects.create(
            source=self.source, target_locale=self.fr_locale
        )

    def test(self):
        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertContains(
            response,
            (
                f'<a href="/admin/localize/update/{self.source.id}/?next=%2Fadmin%2Fpages%2F{self.en_homepage.id}%2F" '
                'aria-label="" class="u-link is-live ">Sync translated pages</a>'
            ),
            html=True,
        )

    def test_hides_if_page_hasnt_got_translations(self):
        self.source.delete()

        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertNotContains(response, "Sync translated pages")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertNotContains(response, "Sync translated pages")


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
class TestSnippetUpdateTranslationsListingButton(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_snippet = TestSnippet.objects.create(field="Test snippet")
        self.fr_snippet = self.en_snippet.copy_for_translation(self.fr_locale)
        self.fr_snippet.save()

        self.source, created = TranslationSource.get_or_create_from_instance(
            self.en_snippet
        )
        self.translation = Translation.objects.create(
            source=self.source, target_locale=self.fr_locale
        )

    def test(self):
        response = self.client.get(
            reverse(
                "wagtailsnippets:list", args=["wagtail_localize_test", "testsnippet"]
            )
        )

        extra = ' title="Sync translated snippets"' if WAGTAIL_VERSION > (2, 15) else ""
        self.assertContains(
            response,
            (
                f'href="/admin/localize/update/{self.source.id}/?next=%2Fadmin%2Fsnippets%2Fwagtail_localize_test%2Ftestsnippet%2F"{extra}>Sync translated snippets</a>'
            ),
        )

    def test_hides_if_snippet_hasnt_got_translations(self):
        self.source.delete()

        response = self.client.get(
            reverse(
                "wagtailsnippets:list", args=["wagtail_localize_test", "testsnippet"]
            )
        )

        self.assertNotContains(response, "Sync translated snippets")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtailsnippets:list", args=["wagtail_localize_test", "testsnippet"]
            )
        )

        self.assertNotContains(response, "Sync translated snippets")


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
class TestUpdateTranslations(TestCase, WagtailTestUtils):
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
            self.en_blog_index,
            title="Blog post",
            slug="blog-post",
            test_charfield="Test content",
            test_richtextfield="<p>rich text</p>",
        )

        self.en_snippet = TestSnippet.objects.create(field="Test snippet")

        # Create translation of page. This creates the FR version
        self.page_source, created = TranslationSource.get_or_create_from_instance(
            self.en_blog_post
        )
        self.page_translation = Translation.objects.create(
            source=self.page_source, target_locale=self.fr_locale
        )
        self.page_translation.save_target(publish=True)
        self.fr_blog_post = self.en_blog_post.get_translation(self.fr_locale)

        # Create translation of snippet. This creates the FR version
        self.snippet_source, created = TranslationSource.get_or_create_from_instance(
            self.en_snippet
        )
        self.snippet_translation = Translation.objects.create(
            source=self.snippet_source, target_locale=self.fr_locale
        )
        self.snippet_translation.save_target(publish=True)
        self.fr_snippet = self.en_snippet.get_translation(self.fr_locale)

    def test_get_update_page_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["translations"],
            [
                {
                    "title": "Blog post",
                    "locale": self.fr_locale,
                    "edit_url": reverse(
                        "wagtailadmin_pages:edit", args=[self.fr_blog_post.id]
                    ),
                }
            ],
        )

    def test_get_update_snippet_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.snippet_source.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["translations"],
            [
                {
                    "title": str(self.fr_snippet),
                    "locale": self.fr_locale,
                    "edit_url": reverse(
                        "wagtailsnippets:edit",
                        args=[
                            "wagtail_localize_test",
                            "testsnippet",
                            self.fr_snippet.id,
                        ],
                    ),
                }
            ],
        )

    def test_get_without_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            )
        )

        assert_permission_denied(self, response)

    def test_get_with_disabled_translation(self):
        self.page_translation.enabled = False
        self.page_translation.save()

        response = self.client.get(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["translations"], [])

    def test_post_update_page_translation(self):
        self.en_blog_post.test_charfield = "Edited blog post"
        self.en_blog_post.save_revision().publish()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            )
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # Check that the new string was submitted
        string_segment = StringSegment.objects.get(context__path="test_charfield")
        self.assertEqual(string_segment.string.data, "Edited blog post")

        # The FR version shouldn't be updated yet
        self.fr_blog_post.refresh_from_db()
        self.assertEqual(self.fr_blog_post.test_charfield, "Test content")

    def test_post_update_page_translation_with_publish_translations(self):
        self.en_blog_post.test_charfield = "Edited blog post"
        self.en_blog_post.save_revision().publish()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
            {"publish_translations": "on"},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # The FR version should be updated
        self.fr_blog_post.refresh_from_db()
        self.assertEqual(self.fr_blog_post.test_charfield, "Edited blog post")

    def test_post_update_page_translation_with_publish_translations_and_cleared_text_field(
        self,
    ):
        self.en_blog_post.test_charfield = ""
        self.en_blog_post.test_richtextfield = ""
        self.en_blog_post.save_revision().publish()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
            {"publish_translations": "on"},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # The FR version should be updated
        self.fr_blog_post.refresh_from_db()
        self.assertEqual(self.fr_blog_post.test_charfield, "")
        self.assertEqual(self.fr_blog_post.test_richtextfield, "")

    def test_post_update_snippet_translation(self):
        self.en_snippet.field = "Edited snippet"
        self.en_snippet.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.snippet_source.id],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtailsnippets:edit",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
        )

        # The FR version shouldn't be updated yet
        self.fr_snippet.refresh_from_db()
        self.assertEqual(self.fr_snippet.field, "Test snippet")

    def test_post_update_snippet_translation_with_publish_translations(self):
        self.en_snippet.field = "Edited snippet"
        self.en_snippet.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.snippet_source.id],
            ),
            {"publish_translations": "on"},
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtailsnippets:edit",
                args=["wagtail_localize_test", "testsnippet", self.en_snippet.id],
            ),
        )

        # The FR version should be updated
        self.fr_snippet.refresh_from_db()
        self.assertEqual(self.fr_snippet.field, "Edited snippet")

    def test_post_with_disabled_translation(self):
        self.page_translation.enabled = False
        self.page_translation.save()

        self.en_blog_post.test_charfield = "Edited blog post"
        self.en_blog_post.save_revision().publish()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            )
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # Check that the new string was submitted
        string_segment = StringSegment.objects.get(context__path="test_charfield")
        self.assertEqual(string_segment.string.data, "Edited blog post")

        # The FR version shouldn't be updated
        self.fr_blog_post.refresh_from_db()
        self.assertEqual(self.fr_blog_post.test_charfield, "Test content")

    def test_post_with_disabled_translation_with_publish_translations(self):
        self.page_translation.enabled = False
        self.page_translation.save()

        self.en_blog_post.test_charfield = "Edited blog post"
        self.en_blog_post.save_revision().publish()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
            {"publish_translations": "on"},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # The FR version shouldn't be updated
        self.fr_blog_post.refresh_from_db()
        self.assertEqual(self.fr_blog_post.test_charfield, "Test content")

    def test_post_update_page_translation_after_source_privacy_added(self):
        view_restriction = PageViewRestriction.objects.create(
            restriction_type="login", page=self.en_blog_post
        )

        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.fr_blog_post.refresh_from_db()
        self.assertTrue(self.fr_blog_post.view_restrictions.exists())
        self.assertTrue(
            self.fr_blog_post.view_restrictions.first().pk, view_restriction.pk
        )

    def test_post_update_page_translation_with_publish_after_source_privacy_added(self):
        view_restriction = PageViewRestriction.objects.create(
            restriction_type="login", page=self.en_blog_post
        )

        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
            {"publish_translations": "on"},
        )
        self.fr_blog_post.refresh_from_db()
        self.assertTrue(self.fr_blog_post.view_restrictions.exists())
        self.assertTrue(
            self.fr_blog_post.view_restrictions.first().pk, view_restriction.pk
        )

    def test_post_update_page_translation_after_source_privacy_removed(self):
        PageViewRestriction.objects.create(
            restriction_type="login", page=self.fr_blog_post
        )

        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.fr_blog_post.refresh_from_db()
        self.assertFalse(self.fr_blog_post.view_restrictions.exists())

    def test_post_update_page_translation_after_source_privacy_changed(self):
        PageViewRestriction.objects.create(
            restriction_type="login", page=self.en_blog_post
        )

        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )

        self.fr_blog_post.refresh_from_db()
        self.assertTrue(self.fr_blog_post.view_restrictions.exists())
        self.assertTrue(
            self.fr_blog_post.view_restrictions.first().restriction_type, "login"
        )

        # change the restriction for the source
        self.en_blog_post.view_restrictions.all().update(
            restriction_type="password", password="test"
        )
        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.fr_blog_post.refresh_from_db()
        translated_restriction = self.fr_blog_post.view_restrictions.first()
        self.assertTrue(translated_restriction.restriction_type, "password")
        self.assertTrue(translated_restriction.password, "test")

        self.en_blog_post.view_restrictions.all().delete()

        test_group = Group.objects.create(name="Test Group")
        restriction = PageViewRestriction.objects.create(
            restriction_type="groups", page=self.en_blog_post
        )
        restriction.groups.set([test_group])

        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.fr_blog_post.refresh_from_db()
        translated_restriction = self.fr_blog_post.view_restrictions.first()
        self.assertTrue(translated_restriction.restriction_type, "groups")
        self.assertEqual(translated_restriction.groups.count(), 1)
        self.assertEqual(translated_restriction.groups.first(), test_group)

        another_group = Group.objects.create(name="Another Group")
        restriction.groups.set([another_group])
        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.fr_blog_post.refresh_from_db()
        translated_restriction = self.fr_blog_post.view_restrictions.first()
        self.assertEqual(translated_restriction.groups.first(), another_group)

    @mock.patch(
        "wagtail_localize.models.TranslationSource.update_target_view_restrictions"
    )
    def test_post_update_page_translation_will_run_update_target_view_restrictions(
        self, update_target_view_restrictions
    ):
        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        self.assertEqual(update_target_view_restrictions.call_count, 1)

        # now let's try with an exception
        update_target_view_restrictions.side_effect = ValidationError("oops")
        self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.page_source.id],
            ),
        )
        # one call from the first post, and one from above
        self.assertEqual(update_target_view_restrictions.call_count, 2)
