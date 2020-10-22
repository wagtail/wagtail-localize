from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.core.models import Page, Locale
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.test.models import TestPage, TestSnippet, NonTranslatableSnippet

from .utils import assert_permission_denied


def make_test_page(parent, cls=None, **kwargs):
    cls = cls or TestPage
    kwargs.setdefault("title", "Test page")
    return parent.add_child(instance=cls(**kwargs))


def strip_user_perms():
    """
    Removes user permissions so they can still access admin and edit pages but can't submit anything for translation.
    """
    editors_group = Group.objects.get(name="Editors")
    editors_group.permissions.filter(codename='submit_translation').delete()

    for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(TestSnippet)):
        editors_group.permissions.add(permission)

    for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(NonTranslatableSnippet)):
        editors_group.permissions.add(permission)

    user = get_user_model().objects.get()
    user.is_superuser = False
    user.groups.add(editors_group)
    user.save()


@override_settings(
    LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
)
class TestTranslatePageListingButton(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_homepage = Page.objects.get(depth=2)
        self.fr_homepage = self.en_homepage.copy_for_translation(self.fr_locale)
        self.de_homepage = self.en_homepage.copy_for_translation(self.de_locale)

        self.en_blog_index = make_test_page(self.en_homepage, title="Blog", slug="blog")

    def test(self):
        response = self.client.get(
            reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        self.assertContains(response, (
            f'<a href="/admin/localize/submit/page/{self.en_blog_index.id}/?next=%2Fadmin%2Fpages%2F{self.en_homepage.id}%2F" '
            'aria-label="" class="u-link is-live ">'
            '\n                    Translate this page\n                </a>'
        ))

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
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
)
class TestSubmitPageTranslation(TestCase, WagtailTestUtils):
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

        self.assertListEqual(
            list(response.context['form']['locales'].field.queryset),
            [self.de_locale, self.fr_locale]
        )

        # More than one locale so show "Select all"
        self.assertFalse(response.context['form']['select_all'].field.widget.is_hidden)

        # Page has children so show "Include subtree"
        self.assertFalse(response.context['form']['include_subtree'].field.widget.is_hidden)

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
            list(response.context['form']['locales'].field.queryset),
            [self.fr_locale]
        )

        # Since there is only one locale, the "Select All" checkbox should be hidden
        self.assertTrue(response.context['form']['select_all'].field.widget.is_hidden)

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
        self.assertTrue(response.context['form']['include_subtree'].field.widget.is_hidden)

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
            follow=True
        )

        self.assertEqual(response.status_code, 404)

    def test_post_submit_page_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
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

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

    def test_post_submit_page_translation_submits_linked_snippets(self):
        self.en_blog_index.test_snippet = TestSnippet.objects.create(field="My test snippet")
        self.en_blog_index.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_index.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        page_translation = Translation.objects.get(source__specific_content_type=ContentType.objects.get_for_model(TestPage))
        self.assertEqual(page_translation.source.locale, self.en_locale)
        self.assertEqual(page_translation.target_locale, self.fr_locale)
        self.assertTrue(page_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        snippet_translation = Translation.objects.get(source__specific_content_type=ContentType.objects.get_for_model(TestSnippet))
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
        fr_translation = Translation.objects.get(
            target_locale=self.fr_locale
        )
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # Check German translation
        de_translation = Translation.objects.get(
            target_locale=self.de_locale
        )
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

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
        )

        # Check multiple translations were created
        self.assertEqual(Translation.objects.count(), 3)

    def test_post_submit_page_translation_with_untranslated_parent(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.en_blog_post.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # One translation should be created
        fr_translation = Translation.objects.get()
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertEqual(fr_translation.target_locale, self.fr_locale)
        self.assertTrue(fr_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_post.get_translation(self.fr_locale)
        self.assertTrue(translated_page.live)

        # The parent should've been created as an alias page
        translated_parent_page = self.en_blog_index.get_translation(self.fr_locale)
        self.assertTrue(translated_parent_page.live)
        self.assertEqual(translated_parent_page.alias_of, self.en_blog_index.page_ptr)

        # Just check the translation was created under its parent
        self.assertEqual(translated_page.get_parent(), translated_parent_page.page_ptr)

    def test_post_submit_page_translation_with_untranslated_grandparent(self):
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

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_blog_index.id])
        )

        # One translation should be created
        fr_translation = Translation.objects.get()
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertEqual(fr_translation.target_locale, es_locale)
        self.assertTrue(fr_translation.created_at)

        # The translated page should've been created and published
        translated_page = self.en_blog_post.get_translation(es_locale)
        self.assertTrue(translated_page.live)

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
        self.assertEqual(translated_parent_page.get_parent(), translated_grandparent_page)
        self.assertEqual(translated_grandparent_page.get_parent(), Page.objects.get(depth=1))

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
        self.assertFormError(response, "form", "locales", ["This field is required."])

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

    def test_post_submit_page_translation_reactivates_deleted_translation(self):
        # Create a disabled translation record
        # This simulates the case where the page was previously translated into that locale but later deleted
        source, created = TranslationSource.get_or_create_from_instance(self.en_blog_index)
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

        self.assertRedirects(
            response, reverse("wagtailadmin_explore", args=[self.en_homepage.id])
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

    def test_post_submit_page_translation_doesnt_reactivate_deactivated_translation(self):
        # Like the previous test, this creates a disabled translation record, but this
        # time, the translation has not been deleted. It should not reactivate in this case
        source, created = TranslationSource.get_or_create_from_instance(self.en_blog_index)
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )
        translation.save_target()

        translation.enabled = False
        translation.save(update_fields=['enabled'])

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


@override_settings(
    LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
)
class TestTranslateSnippetListingButton(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_snippet = TestSnippet.objects.create(field="Test snippet")
        self.fr_snippet = self.en_snippet.copy_for_translation(self.fr_locale)
        self.fr_snippet.save()

        self.not_translatable_snippet = NonTranslatableSnippet.objects.create()

    def test(self):
        response = self.client.get(
            reverse("wagtailsnippets:list", args=['wagtail_localize_test', 'testsnippet'])
        )

        self.assertContains(response, (
            f'href="/admin/localize/submit/snippet/wagtail_localize_test/testsnippet/{self.en_snippet.id}/?next=%2Fadmin%2Fsnippets%2Fwagtail_localize_test%2Ftestsnippet%2F">Translate</a>'
        ))

    def test_hides_if_snippet_already_translated(self):
        de_snippet = self.en_snippet.copy_for_translation(self.de_locale)
        de_snippet.save()

        response = self.client.get(
            reverse("wagtailsnippets:list", args=['wagtail_localize_test', 'testsnippet'])
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_snippet_isnt_translatable(self):
        self.en_snippet.copy_for_translation(self.de_locale)

        response = self.client.get(
            reverse("wagtailsnippets:list", args=['wagtail_localize_test', 'nontranslatablesnippet'])
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse("wagtailsnippets:list", args=['wagtail_localize_test', 'testsnippet'])
        )

        self.assertNotContains(response, "Translate")


@override_settings(
    LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ('en', "English"),
        ('fr', "French"),
        ('de', "German"),
        ('es', "Spanish"),
    ],
)
class TestSubmitSnippetTranslation(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_snippet = TestSnippet.objects.create(field="Test snippet")

        self.not_translatable_snippet = NonTranslatableSnippet.objects.create()

    def test_get_submit_snippet_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context['form']['locales'].field.queryset),
            [self.de_locale, self.fr_locale]
        )

        # More than one locale so show "Select all"
        self.assertFalse(response.context['form']['select_all'].field.widget.is_hidden)

        # Snippets can't have children so hide include_subtree
        self.assertTrue(response.context['form']['include_subtree'].field.widget.is_hidden)

    def test_get_submit_snippet_translation_when_not_snippet(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtailcore', 'page', 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_when_invalid_model(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtailcore', 'foo', 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_when_not_translatable(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'nontranslatablesnippet', self.not_translatable_snippet.id],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_snippet_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
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
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context['form']['locales'].field.queryset),
            [self.fr_locale]
        )

        # Since there is only one locale, the "Select All" checkbox should be hidden
        self.assertTrue(response.context['form']['select_all'].field.widget.is_hidden)

    def test_post_submit_snippet_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailsnippets:edit", args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id])
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated snippet should've been created
        translated_snippet = self.en_snippet.get_translation(self.fr_locale)
        self.assertEqual(translated_snippet.field, "Test snippet")

    def test_post_submit_snippet_translation_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id]},
        )

        self.assertRedirects(
            response, reverse("wagtailsnippets:edit", args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id])
        )

        # Check French translation
        fr_translation = Translation.objects.get(
            target_locale=self.fr_locale
        )
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # Check German translation
        de_translation = Translation.objects.get(
            target_locale=self.de_locale
        )
        self.assertEqual(de_translation.source.locale, self.en_locale)
        self.assertTrue(de_translation.created_at)

    def test_post_submit_snippet_translation_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            ),
            {"locales": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Translation.objects.exists())
        self.assertFormError(response, "form", "locales", ["This field is required."])

    def test_post_submit_snippet_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.post(
            reverse(
                "wagtail_localize:submit_snippet_translation",
                args=['wagtail_localize_test', 'testsnippet', self.en_snippet.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        assert_permission_denied(self, response)
