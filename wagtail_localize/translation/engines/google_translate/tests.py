from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from googletrans.models import Translated
from wagtail.core.models import Page

from wagtail_localize.admin.workflow.models import (
    TranslationRequest,
    TranslationRequestPage,
)
from wagtail_localize.models import Language, Locale
from wagtail_localize.test.models import TestPage, TestSnippet


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    return page


@mock.patch("googletrans.Translator")
class TestTranslate(TestCase):
    fixtures = ["test_user.json"]

    def setUp(self):
        self.client.login(username="admin", password="password")

        Language.objects.create(code="fr")
        self.user = User.objects.get(username="admin")
        self.translation_request = TranslationRequest.objects.create(
            source_locale=Locale.objects.default(),
            target_locale=Locale.objects.get(language__code="fr"),
            target_root=Page.objects.get(id=1),
            created_at=timezone.now(),
            created_by=self.user,
        )

    def add_page_to_request(self, page, **kwargs):
        return TranslationRequestPage.objects.create(
            request=self.translation_request,
            source_revision=page.get_latest_revision(),
            **kwargs,
        )

    def test_translate(self, Translator):
        page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some translatable content",
            test_richtextfield="<p>Translatable <b>rich text</b></p>",
        )
        request_page = self.add_page_to_request(page)

        # Mock response from Google Translate
        Translator().translate.return_value = [
            Translated(
                "en",
                "fr",
                "Some translatable content",
                "Certains contenus traduisibles",
                "Certains contenus traduisibles",
            ),
            Translated(
                "en",
                "fr",
                "Translatable rich text",
                "Texte riche traduisible",
                "Texte riche traduisible",
            ),
        ]

        response = self.client.post(
            reverse(
                "wagtail_localize_google_translate:translate",
                args=[self.translation_request.id],
            ),
            {"publish": "on"},
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_workflow_management:detail",
                args=[self.translation_request.id],
            ),
        )

        Translator().translate.assert_called_with(
            ["Some translatable content", "Translatable rich text"], dest="fr", src="en"
        )

        request_page.refresh_from_db()
        self.assertTrue(request_page.is_completed)

        translated_page = page.get_translation(Locale.objects.get(language__code="fr"))
        self.assertTrue(translated_page.live)
        self.assertEqual(
            translated_page.test_charfield, "Certains contenus traduisibles"
        )
        self.assertEqual(
            translated_page.test_richtextfield, "<p>Texte riche traduisible</p>"
        )

    def test_translate_without_publishing(self, Translator):
        page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some translatable content",
        )
        request_page = self.add_page_to_request(page)

        # Mock response from Google Translate
        Translator().translate.return_value = [
            Translated(
                "en",
                "fr",
                "Some translatable content",
                "Certains contenus traduisibles",
                "Certains contenus traduisibles",
            )
        ]

        response = self.client.post(
            reverse(
                "wagtail_localize_google_translate:translate",
                args=[self.translation_request.id],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_workflow_management:detail",
                args=[self.translation_request.id],
            ),
        )

        Translator().translate.assert_called_with(
            ["Some translatable content"], dest="fr", src="en"
        )

        request_page.refresh_from_db()
        self.assertTrue(request_page.is_completed)

        translated_page = page.get_translation(Locale.objects.get(language__code="fr"))
        self.assertFalse(translated_page.live)
        self.assertEqual(
            translated_page.get_latest_revision_as_page().test_charfield,
            "Certains contenus traduisibles",
        )

    def test_translate_with_nested_snippet(self, Translator):
        snippet = TestSnippet.objects.create(field="Some test snippet content")
        page = create_test_page(
            title="Test page", slug="test-page", test_snippet=snippet
        )
        request_page = self.add_page_to_request(page)

        # Mock response from Google Translate
        Translator().translate.return_value = [
            Translated(
                "en",
                "fr",
                "Some test snippet content",
                "Du contenu d'extrait de test",
                "Du contenu d'extrait de test",
            )
        ]

        response = self.client.post(
            reverse(
                "wagtail_localize_google_translate:translate",
                args=[self.translation_request.id],
            ),
            {"publish": "on"},
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_workflow_management:detail",
                args=[self.translation_request.id],
            ),
        )

        Translator().translate.assert_called_with(
            ["Some test snippet content"], dest="fr", src="en"
        )

        request_page.refresh_from_db()
        self.assertTrue(request_page.is_completed)

        translated_page = page.get_translation(Locale.objects.get(language__code="fr"))
        self.assertEqual(
            translated_page.test_snippet.field, "Du contenu d'extrait de test"
        )
