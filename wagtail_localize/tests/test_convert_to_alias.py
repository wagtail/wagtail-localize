from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Locale, Page, PageLogEntry
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import LocaleSynchronization, Translation
from wagtail_localize.test.models import TestPage
from wagtail_localize.wagtail_hooks import ConvertToAliasPageActionMenuItem


class ConvertToAliasTestData(WagtailTestUtils):
    def setUp(self):
        self.en_locale = Locale.objects.get(language_code="en")
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.home_page = Page.objects.get(depth=2)
        self.page = self.home_page.add_child(
            instance=TestPage(
                title="The title",
                slug="the-page",
            )
        )

        LocaleSynchronization.objects.create(
            locale=self.fr_locale,
            sync_from=self.en_locale,
        )
        self.fr_page = self.page.get_translation(self.fr_locale)

        self.login()


class ConvertToAliasTest(ConvertToAliasTestData, TestCase):
    def _page_action_is_shown(self, page, view="edit"):
        menu_item = ConvertToAliasPageActionMenuItem()
        context = {"view": view, "page": page}

        return menu_item._is_shown(context)

    def test_page_action_not_available_on_non_translation_pages(self):
        self.assertFalse(self._page_action_is_shown(self.page))

    def test_page_action_not_available_on_alias_pages(self):
        # as created, the FR page is just an alias.
        self.assertFalse(self._page_action_is_shown(self.fr_page))
        alias_page = self.page.create_alias(
            parent=self.home_page,
            update_slug="the-page-alias",
        )
        self.assertFalse(self._page_action_is_shown(alias_page))

    def test_page_action_not_available_when_source_page_deleted(self):
        self.page.delete()
        self.assertFalse(self._page_action_is_shown(self.fr_page))

    def test_page_action_available(self):
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )
        self.fr_page.refresh_from_db()
        self.assertTrue(self._page_action_is_shown(self.fr_page))

    def test_convert_url_in_edit_context(self):
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.assertIn("convertToAliasUrl", response.context["props"])
        self.assertIn(
            reverse("wagtail_localize:convert_to_alias", args=[self.fr_page.id]),
            response.context["props"],
        )

    def test_convert_url_not_in_edit_context_when_source_deleted(self):
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )
        self.page.delete()
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertNotContains(
            response,
            reverse("wagtail_localize:convert_to_alias", args=[self.fr_page.id]),
        )


class ConvertToAliasViewTest(ConvertToAliasTestData, TestCase):
    def setUp(self):
        super().setUp()
        # submit for translation, thus no longer an alias
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.page.id],
            ),
            {"locales": [self.fr_locale.id]},
        )
        self.fr_page.refresh_from_db()
        self.convert_url = reverse(
            "wagtail_localize:convert_to_alias", args=[self.fr_page.id]
        )

    def test_convert_to_alias_action_redirect_to_own_view(self):
        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {"localize-convert-to-alias": "Convert to alias page"},
        )
        self.assertRedirects(response, self.convert_url)

    def test_convert_view_404_with_invalid_page_id(self):
        response = self.client.get(
            reverse("wagtail_localize:convert_to_alias", args=[100000]), follow=True
        )
        self.assertEqual(response.status_code, 404)

    def test_convert_view_404s_for_alias_pages(self):
        alias_page = self.page.create_alias(
            parent=self.home_page,
            update_slug="the-page-alias",
        )
        response = self.client.get(
            reverse("wagtail_localize:convert_to_alias", args=[alias_page.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)

    def test_convert_view_404s_for_non_translation_pages(self):
        response = self.client.get(
            reverse("wagtail_localize:convert_to_alias", args=[self.page.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)

    def test_convert_view_shows_confirmation_page_on_get(self):
        response = self.client.get(self.convert_url)
        self.assertTemplateUsed("wagtail_localize/admin/confirm_convert_to_alias.html")
        self.assertEqual(response.context["page"].id, self.fr_page.id)

    def test_convert(self):
        self.assertIsNone(self.fr_page.alias_of_id)
        response = self.client.post(self.convert_url)
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.alias_of_id, self.page.id)

    def test_convert_syncs_alias_with_source(self):
        # update the source page
        self.page.title = "Updated title"
        self.page.save()
        self.page.save_revision().publish()

        self.client.post(self.convert_url)
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.title, "Updated title")

    def test_convert_adds_entry_to_audit_log(self):
        self.assertFalse(
            PageLogEntry.objects.filter(
                page=self.fr_page.id, action="wagtail_localize.convert_to_alias"
            ).exists()
        )

        self.client.post(self.convert_url)
        self.assertTrue(
            PageLogEntry.objects.filter(
                page=self.fr_page.id, action="wagtail_localize.convert_to_alias"
            ).exists()
        )

    def test_convert_redirect_with_valid_next_url(self):
        home = reverse("wagtailadmin_home")
        response = self.client.post(self.convert_url + f"?next={home}")
        self.assertRedirects(response, home)

    def test_convert_redirect_with_invalid_next_url(self):
        response = self.client.post(self.convert_url + "?next=https://example.com")
        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

    def test_convert_removes_translation_objects(self):
        self.assertTrue(
            Translation.objects.filter(
                source__object_id=self.fr_page.translation_key,
                source__specific_content_type=self.fr_page.content_type_id,
                target_locale=self.fr_page.locale_id,
            ).exists()
        )

        self.client.post(self.convert_url)

        self.assertFalse(
            Translation.objects.filter(
                source__object_id=self.fr_page.translation_key,
                source__specific_content_type=self.fr_page.content_type_id,
                target_locale=self.fr_page.locale_id,
            ).exists()
        )
