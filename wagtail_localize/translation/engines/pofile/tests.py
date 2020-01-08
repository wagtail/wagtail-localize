import polib
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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


class BasePoFileTestCase(TestCase):
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


class TestDownload(BasePoFileTestCase):
    def test_download(self):
        page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some translatable content",
            test_richtextfield="<p>Translatable <b>rich text</b></p>",
        )
        self.add_page_to_request(page)

        response = self.client.get(
            reverse(
                "wagtail_localize_pofile:download", args=[self.translation_request.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/x-gettext-translation")

        self.assertIn(
            b'#: pages/test-page/:test_charfield\nmsgid "Some translatable content"\nmsgstr ""\n',
            response.content,
        )

        self.assertIn(
            b'#: pages/test-page/:test_richtextfield\nmsgid "Translatable rich text"\nmsgstr ""\n',
            response.content,
        )

    def test_download_with_nested_snippet(self):
        snippet = TestSnippet.objects.create(field="Some test snippet content")
        page = create_test_page(
            title="Test page", slug="test-page", test_snippet=snippet
        )
        self.add_page_to_request(page)

        response = self.client.get(
            reverse(
                "wagtail_localize_pofile:download", args=[self.translation_request.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/x-gettext-translation")

        self.assertIn(
            f'#: test-snippets/{snippet.id}:field\nmsgid "Some test snippet content"\nmsgstr ""\n',
            response.content.decode(),
        )


class TestUpload(BasePoFileTestCase):
    def test_upload(self):
        page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some translatable content",
            test_richtextfield="<p>Translatable <b>rich text</b></p>",
        )
        request_page = self.add_page_to_request(page)

        po = polib.POFile()
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
        }

        po.extend(
            [
                polib.POEntry(
                    msgid="Some translatable content",
                    msgstr="Du contenu traduisible",
                    occurrences="",
                ),
                polib.POEntry(
                    msgid="Translatable rich text",
                    msgstr="Texte riche traduisible",
                    occurrences="",
                ),
            ]
        )

        response = self.client.post(
            reverse(
                "wagtail_localize_pofile:upload", args=[self.translation_request.id]
            ),
            {"file": SimpleUploadedFile("test.po", str(po).encode("utf-8")),},
        )
        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_workflow_management:detail",
                args=[self.translation_request.id],
            ),
        )

        request_page.refresh_from_db()
        self.assertTrue(request_page.is_completed)

        completed_revision = request_page.completed_revision
        completed_page = completed_revision.as_page_object()
        self.assertEqual(completed_page.locale, self.translation_request.target_locale)
        self.assertEqual(completed_page.translation_key, page.translation_key)
        self.assertEqual(completed_page.test_charfield, "Du contenu traduisible")
        self.assertEqual(
            completed_page.test_richtextfield, "<p>Texte riche traduisible</p>"
        )

    def test_upload_with_nested_snippet(self):
        snippet = TestSnippet.objects.create(field="Some test snippet content")
        page = create_test_page(
            title="Test page", slug="test-page", test_snippet=snippet
        )
        request_page = self.add_page_to_request(page)

        po = polib.POFile()
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
        }

        po.append(
            polib.POEntry(
                msgid="Some test snippet content",
                msgstr="Du contenu d'extrait de test",
                occurrences="",
            )
        )

        response = self.client.post(
            reverse(
                "wagtail_localize_pofile:upload", args=[self.translation_request.id]
            ),
            {"file": SimpleUploadedFile("test.po", str(po).encode("utf-8")),},
        )
        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_workflow_management:detail",
                args=[self.translation_request.id],
            ),
        )

        request_page.refresh_from_db()
        self.assertTrue(request_page.is_completed)

        completed_revision = request_page.completed_revision
        completed_page = completed_revision.as_page_object()
        self.assertEqual(
            completed_page.test_snippet.locale, self.translation_request.target_locale
        )
        self.assertEqual(
            completed_page.test_snippet.translation_key, snippet.translation_key
        )
        self.assertEqual(
            completed_page.test_snippet.field, "Du contenu d'extrait de test"
        )
