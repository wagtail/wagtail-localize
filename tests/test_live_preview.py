import json

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from wagtail.models import Page

import wagtail_localize.views.live_preview as live_preview


class PreviewSession(dict):
    modified = False


class LivePreviewTests(SimpleTestCase):
    def request(self, method="post", payload=None, query=""):
        factory = RequestFactory()
        path = f"/admin/localize/translate/7/live-preview/{query}"
        data = {"payload": json.dumps(payload or {})}
        request = getattr(factory, method)(path, data=data)
        request.session = PreviewSession()
        request.user = SimpleNamespace()
        return request

    def translation(self):
        target = MagicMock(spec=Page)
        target.default_preview_mode = "default"
        target.preview_modes = [("default", "Default")]
        return SimpleNamespace(
            source=SimpleNamespace(),
            target_locale=SimpleNamespace(),
            get_target_instance=lambda: target,
        )

    @patch.object(live_preview, "user_can_edit_instance", return_value=False)
    @patch.object(live_preview, "get_object_or_404")
    def test_requires_edit_permission(self, get_translation, _can_edit):
        get_translation.return_value = self.translation()
        with self.assertRaises(PermissionDenied):
            live_preview.live_preview(self.request(), translation_id=7)

    @patch.object(live_preview, "_get_preview_values", side_effect=ValueError)
    @patch.object(live_preview, "user_can_edit_instance", return_value=True)
    @patch.object(live_preview, "get_object_or_404")
    def test_rejects_invalid_payload(
        self, get_translation, _can_edit, _get_values
    ):
        get_translation.return_value = self.translation()
        response = live_preview.live_preview(
            self.request(payload={"stringTranslations": []}), translation_id=7
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["is_valid"], False)

    @patch.object(live_preview, "_get_preview_values", return_value=({"1": "draft"}, {}))
    @patch.object(live_preview, "user_can_edit_instance", return_value=True)
    @patch.object(live_preview, "get_object_or_404")
    def test_stores_unsaved_payload_in_session(
        self, get_translation, _can_edit, _get_values
    ):
        get_translation.return_value = self.translation()
        request = self.request(payload={"stringTranslations": {"1": "draft"}})
        response = live_preview.live_preview(request, translation_id=7)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(request.session["wagtail-localize-live-preview-7"]),
            {"stringTranslations": {"1": "draft"}, "segmentOverrides": {}},
        )
        self.assertTrue(request.session.modified)

    @patch.object(live_preview, "_replace_ephemeral_values")
    @patch.object(live_preview, "_get_preview_values", return_value=({}, {}))
    @patch.object(live_preview, "user_can_edit_instance", return_value=True)
    @patch.object(live_preview, "get_object_or_404")
    def test_renders_ephemeral_payload(
        self, get_translation, _can_edit, _get_values, replace
    ):
        get_translation.return_value = self.translation()
        request = self.request("get")
        request.session["wagtail-localize-live-preview-7"] = json.dumps(
            {"stringTranslations": {}, "segmentOverrides": {}}
        )
        ephemeral = MagicMock()
        ephemeral.make_preview_request.return_value = HttpResponse("preview")
        replace.return_value = ephemeral

        response = live_preview.live_preview(request, translation_id=7)

        self.assertEqual(response.content, b"preview")
        ephemeral.make_preview_request.assert_called_once_with(
            request, "default", {"in_preview_panel": False, "is_editing": True}
        )

    def test_url_and_csrf_contract(self):
        self.assertEqual(
            reverse("wagtail_localize:live_preview", args=[7]),
            "/admin/localize/translate/7/live-preview/",
        )
        self.assertFalse(getattr(live_preview.live_preview, "csrf_exempt", False))
