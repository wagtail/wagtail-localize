import json
import tempfile
import uuid

from unittest.mock import patch

import polib

from django.contrib.admin.utils import quote
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy
from freezegun import freeze_time
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import (
    DjangoModelPermissionsOrAnonReadOnly,
    IsAuthenticated,
)
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin.panels import FieldPanel, TitleFieldPanel
from wagtail.blocks import StreamValue
from wagtail.documents.models import Document
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Locale, Page, Revision
from wagtail.test.utils import WagtailTestUtils

from wagtail_localize.machine_translators.dummy import translate_html
from wagtail_localize.models import (
    OverridableSegment,
    SegmentOverride,
    String,
    StringTranslation,
    Translation,
    TranslationContext,
    TranslationLog,
    TranslationSource,
)
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import (
    Header,
    NavigationLink,
    NonTranslatableSnippet,
    PageWithCustomEditHandler,
    PageWithCustomEditHandlerChildObject,
    SubNavigationLink,
    TestHomePage,
    TestPage,
    TestSnippet,
    TestSnippetOrderable,
)
from wagtail_localize.views.edit_translation import (
    edit_override,
    edit_string_translation,
)

from .utils import assert_permission_denied


RICH_TEXT_DATA = '<h1>This is a heading</h1><p>This is a paragraph. &lt;foo&gt; <b>Bold text</b></p><ul><li><a href="http://example.com">This is a link</a>.</li><li>Special characters: \'"!? セキレイ</li></ul>'

STREAM_TEXT_BLOCK_ID = uuid.uuid4()
STREAM_STRUCT_BLOCK_ID = uuid.uuid4()
STREAM_RICH_TEXT_BLOCK_ID = uuid.uuid4()
STREAM_CHOOSER_STRUCT_BLOCK_ID = uuid.uuid4()
STREAM_NESTED_CHOOSER_STRUCT_BLOCK_ID = uuid.uuid4()

STREAM_DATA = [
    {
        "id": STREAM_TEXT_BLOCK_ID,
        "type": "test_textblock",
        "value": "This is a text block",
    },
    {
        "id": STREAM_STRUCT_BLOCK_ID,
        "type": "test_structblock",
        "value": {"field_a": "This is a struct", "field_b": "block"},
    },
    {
        "id": STREAM_RICH_TEXT_BLOCK_ID,
        "type": "test_richtextblock",
        "value": RICH_TEXT_DATA,
    },
]


# Patches for translation skipping tests
def patched_translate(source_locale, target_locale, strings):
    result = {}
    for string in strings:
        if not all(ord(c) < 128 for c in string.data):
            continue
        result[string] = StringValue(translate_html(string.data))

    return result


def patched_translate_html(html):
    if not all(ord(c) < 128 for c in html):
        return None
    return translate_html(html)


class EditTranslationTestData(WagtailTestUtils):
    @classmethod
    def setUpTestData(cls):
        cls.user = cls.create_test_user()
        cls.moderators_group = Group.objects.get(name="Moderators")

        # Convert the user into an editor
        for permission in Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ):
            cls.moderators_group.permissions.add(permission)
        for permission in Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(NonTranslatableSnippet)
        ):
            cls.moderators_group.permissions.add(permission)
        cls.user.groups.add(cls.moderators_group)
        cls.user.is_superuser = False
        cls.user.save(update_fields=["is_superuser"])

        cls.home_page = Page.objects.get(depth=2)
        cls.fr_locale = Locale.objects.create(language_code="fr")

        if WAGTAIL_VERSION >= (6, 4, 0, "alpha", 0):
            cls.avatar_url = (
                "//www.gravatar.com/avatar/93942e96f5acd83e2e047ad8fe03114d?d=mp&s=50"
            )
        else:
            cls.avatar_url = (
                "//www.gravatar.com/avatar/93942e96f5acd83e2e047ad8fe03114d?s=50&d=mm"
            )

    def setUp(self):
        self.login(username=self.user.username)

        # Create page
        self.snippet = TestSnippet.objects.create(field="Test snippet")
        self.page = self.home_page.add_child(
            instance=TestPage(
                title="The title",
                slug="test",
                test_charfield="A char field",
                test_textfield="A text field",
                test_emailfield="email@example.com",
                test_synchronized_emailfield="email@example.com",
                test_slugfield="a-slug-field",
                test_urlfield="https://www.example.com",
                test_richtextfield=RICH_TEXT_DATA,
                test_streamfield=StreamValue(
                    TestPage.test_streamfield.field.stream_block,
                    STREAM_DATA,
                    is_lazy=True,
                ),
                test_snippet=self.snippet,
            )
        )

        # Create translations
        self.snippet_source, created = TranslationSource.get_or_create_from_instance(
            self.snippet
        )
        self.snippet_translation = Translation.objects.create(
            source=self.snippet_source,
            target_locale=self.fr_locale,
        )
        self.snippet_translation.save_target()
        self.fr_snippet = self.snippet.get_translation(self.fr_locale)

        self.page_source, created = TranslationSource.get_or_create_from_instance(
            self.page
        )
        self.page_translation = Translation.objects.create(
            source=self.page_source,
            target_locale=self.fr_locale,
        )

        with patch.object(transaction, "on_commit", side_effect=lambda func: func()):
            self.page_translation.save_target()

        self.fr_page = self.page.get_translation(self.fr_locale)
        self.fr_home_page = self.home_page.get_translation(self.fr_locale)

        # Create a segment override
        self.overridable_segment = OverridableSegment.objects.get(
            source=self.page_source, context__path="test_synchronized_emailfield"
        )
        self.segment_override = SegmentOverride.objects.create(
            locale=self.fr_locale,
            context=self.overridable_segment.context,
            data_json='"overridden@example.com"',
        )

        # Delete translation logs that were created in set up
        TranslationLog.objects.all().delete()


class TestGetEditTranslationView(EditTranslationTestData, TestCase):
    def test_edit_page_translation(self):
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(props["object"]["title"], "The title")
        self.assertTrue(props["object"]["isLive"])
        self.assertFalse(props["object"]["isLocked"])
        self.assertTrue(props["object"]["lastPublishedDate"])
        self.assertEqual(props["object"]["liveUrl"], "http://localhost/fr/test/")

        self.assertEqual(
            props["breadcrumb"],
            [
                {
                    "id": 1,
                    "isRoot": True,
                    "title": "Root",
                    "exploreUrl": reverse("wagtailadmin_explore_root"),
                },
                {
                    "id": self.fr_home_page.id,
                    "isRoot": False,
                    "title": "Welcome to your new Wagtail site!",
                    "exploreUrl": reverse(
                        "wagtailadmin_explore", args=[self.fr_home_page.id]
                    ),
                },
            ],
        )

        self.assertEqual(
            props["tabs"],
            [
                {"label": "Content", "slug": "content"},
                {"label": "Promote", "slug": "promote"},
                {"label": "Settings", "slug": "settings"},
            ],
        )

        self.assertEqual(
            props["sourceLocale"], {"code": "en", "displayName": "English"}
        )
        self.assertEqual(props["locale"], {"code": "fr", "displayName": "French"})

        self.assertEqual(
            props["translations"],
            [
                {
                    "title": "The title",
                    "locale": {"code": "en", "displayName": "English"},
                    "editUrl": reverse("wagtailadmin_pages:edit", args=[self.page.id]),
                }
            ],
        )

        self.assertTrue(props["perms"]["canPublish"])
        self.assertTrue(props["perms"]["canUnpublish"])
        self.assertTrue(props["perms"]["canLock"])
        self.assertTrue(props["perms"]["canUnlock"])
        self.assertTrue(props["perms"]["canDelete"])

        self.assertEqual(
            props["links"]["unpublishUrl"],
            reverse("wagtailadmin_pages:unpublish", args=[self.fr_page.id]),
        )
        self.assertEqual(
            props["links"]["lockUrl"],
            reverse("wagtailadmin_pages:lock", args=[self.fr_page.id]),
        )
        self.assertEqual(
            props["links"]["unlockUrl"],
            reverse("wagtailadmin_pages:unlock", args=[self.fr_page.id]),
        )
        self.assertEqual(
            props["links"]["deleteUrl"],
            reverse("wagtailadmin_pages:delete", args=[self.fr_page.id]),
        )
        self.assertEqual(
            props["links"]["convertToAliasUrl"],
            reverse("wagtail_localize:convert_to_alias", args=[self.fr_page.id]),
        )

        self.assertEqual(
            props["previewModes"],
            [
                {
                    "mode": "",
                    "label": "Default",
                    "url": reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.page_translation.id],
                    ),
                }
            ],
        )

        self.assertEqual(props["initialStringTranslations"], [])
        self.assertEqual(
            props["initialOverrides"],
            [
                {
                    "data": "overridden@example.com",
                    "error": None,
                    "segment_id": self.overridable_segment.id,
                }
            ],
        )

        # Check segments
        self.assertEqual(
            [
                (segment["contentPath"], segment["source"])
                for segment in props["segments"]
                if segment["type"] == "string"
            ],
            [
                ("test_charfield", "A char field"),
                ("test_textfield", "A text field"),
                ("test_emailfield", "email@example.com"),
                ("test_slugfield", "a-slug-field"),
                ("test_urlfield", "https://www.example.com"),
                ("test_richtextfield", "This is a heading"),
                (
                    "test_richtextfield",
                    "This is a paragraph. &lt;foo&gt; <b>Bold text</b>",
                ),
                ("test_richtextfield", '<a id="a1">This is a link</a>.'),
                ("test_richtextfield", "Special characters: '\"!? セキレイ"),
                (f"test_streamfield.{STREAM_TEXT_BLOCK_ID}", "This is a text block"),
                (
                    f"test_streamfield.{STREAM_STRUCT_BLOCK_ID}.field_a",
                    "This is a struct",
                ),
                (f"test_streamfield.{STREAM_STRUCT_BLOCK_ID}.field_b", "block"),
                (f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}", "This is a heading"),
                (
                    f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}",
                    "This is a paragraph. &lt;foo&gt; <b>Bold text</b>",
                ),
                (
                    f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}",
                    '<a id="a1">This is a link</a>.',
                ),
                (
                    f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}",
                    "Special characters: '\"!? セキレイ",
                ),
            ],
        )
        self.assertEqual(
            [
                (segment["contentPath"], segment["value"])
                for segment in props["segments"]
                if segment["type"] == "synchronised_value"
            ],
            [
                ("test_richtextfield.'http://example.com'", "http://example.com"),
                (
                    f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}.'http://example.com'",
                    "http://example.com",
                ),
                ("test_synchronized_emailfield", "email@example.com"),
            ],
        )

        # Test locations
        self.assertEqual(
            props["segments"][0]["location"],
            {
                "tab": "content",
                "field": "Char field",
                "blockId": None,
                "fieldHelpText": "",
                "order": 1,
                "subField": None,
                "widget": None,
            },
        )
        self.assertEqual(
            props["segments"][7]["location"],
            {
                "tab": "content",
                "field": "Test richtextfield",
                "blockId": None,
                "fieldHelpText": "",
                "order": 6,
                "subField": None,
                "widget": None,
            },
        )
        self.assertEqual(
            props["segments"][10]["location"],
            {
                "tab": "content",
                "field": "Text block",
                "blockId": str(STREAM_TEXT_BLOCK_ID),
                "fieldHelpText": "",
                "order": 7,
                "subField": None,
                "widget": None,
            },
        )
        self.assertEqual(
            props["segments"][11]["location"],
            {
                "tab": "content",
                "field": "Test structblock",
                "blockId": str(STREAM_STRUCT_BLOCK_ID),
                "fieldHelpText": "",
                "order": 7,
                "subField": "Field a",
                "widget": None,
            },
        )
        self.assertEqual(
            props["segments"][14]["location"],
            {
                "tab": "content",
                "field": "Test richtextblock",
                "blockId": str(STREAM_RICH_TEXT_BLOCK_ID),
                "fieldHelpText": "",
                "order": 7,
                "subField": None,
                "widget": None,
            },
        )

        # TODO: Example that uses fieldHelpText

        # Check synchronised value
        synchronised_value_segment = props["segments"][9]
        self.assertEqual(synchronised_value_segment["type"], "synchronised_value")
        self.assertEqual(
            synchronised_value_segment["contentPath"],
            "test_richtextfield.'http://example.com'",
        )
        self.assertEqual(
            synchronised_value_segment["location"],
            {
                "blockId": None,
                "field": "Test richtextfield",
                "fieldHelpText": "",
                "order": 6,
                "subField": None,
                "tab": "content",
                "widget": {"type": "text"},
            },
        )
        self.assertEqual(synchronised_value_segment["value"], "http://example.com")

        # Check synchronised value extracted from rich text block
        synchronised_value_segment = props["segments"][17]
        self.assertEqual(synchronised_value_segment["type"], "synchronised_value")
        self.assertEqual(
            synchronised_value_segment["contentPath"],
            f"test_streamfield.{STREAM_RICH_TEXT_BLOCK_ID}.'http://example.com'",
        )
        self.assertEqual(
            synchronised_value_segment["location"],
            {
                "blockId": str(STREAM_RICH_TEXT_BLOCK_ID),
                "field": "Test richtextblock",
                "fieldHelpText": "",
                "order": 7,
                "subField": None,
                "tab": "content",
                "widget": {"type": "text"},
            },
        )
        self.assertEqual(synchronised_value_segment["value"], "http://example.com")

        # Check related object
        related_object_segment = props["segments"][18]
        self.assertEqual(related_object_segment["type"], "related_object")
        self.assertEqual(related_object_segment["contentPath"], "test_snippet")
        self.assertEqual(
            related_object_segment["location"],
            {
                "tab": "content",
                "field": "Test snippet",
                "blockId": None,
                "fieldHelpText": "",
                "order": 8,
                "subField": None,
                "widget": None,
            },
        )
        self.assertEqual(related_object_segment["source"]["title"], str(self.snippet))
        self.assertEqual(related_object_segment["dest"]["title"], str(self.fr_snippet))
        self.assertEqual(
            related_object_segment["translationProgress"],
            {"totalSegments": 1, "translatedSegments": 0},
        )

    def test_page_chooser_widgets(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type
        self.page.test_page_with_restricted_types = home_page_with_specific_type

        PAGE_CHOOSER_BLOCK_ID = uuid.uuid4()
        PAGE_CHOOSER_BLOCK_WITH_RESTRICTED_TYPES_ID = uuid.uuid4()

        STREAM_DATA_WITH_PAGE_CHOOSERS = [
            {
                "id": PAGE_CHOOSER_BLOCK_ID,
                "type": "test_pagechooserblock",
                "value": self.home_page.id,
            },
            {
                "id": PAGE_CHOOSER_BLOCK_WITH_RESTRICTED_TYPES_ID,
                "type": "test_pagechooserblock_with_restricted_types",
                "value": home_page_with_specific_type.id,
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA_WITH_PAGE_CHOOSERS,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment for segment in props["segments"]
        }
        self.assertEqual(
            segments_by_content_path["test_page"]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )
        self.assertEqual(
            segments_by_content_path["test_page_specific_type"]["location"]["widget"],
            {
                "type": "page_chooser",
                "allowed_page_types": ["wagtail_localize_test.testhomepage"],
            },
        )
        self.assertEqual(
            segments_by_content_path["test_page_with_restricted_types"]["location"][
                "widget"
            ],
            {
                "type": "page_chooser",
                "allowed_page_types": [
                    "wagtail_localize_test.testhomepage",
                    "wagtail_localize_test.testpage",
                ],
            },
        )
        self.assertEqual(
            segments_by_content_path[f"test_streamfield.{PAGE_CHOOSER_BLOCK_ID}"][
                "location"
            ]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )
        self.assertEqual(
            segments_by_content_path[
                f"test_streamfield.{PAGE_CHOOSER_BLOCK_WITH_RESTRICTED_TYPES_ID}"
            ]["location"]["widget"],
            {
                "type": "page_chooser",
                "allowed_page_types": [
                    "wagtail_localize_test.testhomepage",
                    "wagtail_localize_test.testpage",
                ],
            },
        )

    def test_page_chooser_in_orderable(self):
        self.snippet.test_snippet_orderable.add(
            TestSnippetOrderable(orderable_text="foo", orderable_page=self.home_page)
        )
        TranslationSource.update_or_create_from_instance(self.snippet)

        response = self.client.get(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment for segment in props["segments"]
        }
        orderable_block_id = [
            segment["location"]["blockId"]
            for segment in props["segments"]
            if segment["location"]["field"] == "Test snippet orderable"
        ][0]
        orderable_page_path = (
            f"test_snippet_orderable.{orderable_block_id}.orderable_page"
        )
        self.assertEqual(
            segments_by_content_path[orderable_page_path]["location"]["widget"],
            {
                "type": "page_chooser",
                "allowed_page_types": [
                    "wagtailcore.page",
                ],
            },
        )
        self.assertEqual(
            segments_by_content_path[orderable_page_path]["location"]["subField"],
            "Orderable page",
        )

    def test_snippet_chooser_widgets(self):
        first_snippet = TestSnippet.objects.create(field="First snippet")
        second_snippet = NonTranslatableSnippet.objects.create(field="Second snippet")

        SNIPPET_CHOOSER_BLOCK_ID = uuid.uuid4()
        STREAM_DATA_WITH_SNIPPET_CHOOSERS = [
            {
                "id": SNIPPET_CHOOSER_BLOCK_ID,
                "type": "test_nontranslatablesnippetchooserblock",
                "value": second_snippet.id,
            },
        ]

        self.page.test_synchronized_snippet = first_snippet
        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA_WITH_SNIPPET_CHOOSERS,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment for segment in props["segments"]
        }
        self.assertEqual(
            segments_by_content_path["test_synchronized_snippet"]["location"]["widget"],
            {
                "type": "snippet_chooser",
                "snippet_model": {
                    "app_label": "wagtail_localize_test",
                    "model_name": "testsnippet",
                    "verbose_name": "test snippet",
                    "verbose_name_plural": "test snippets",
                },
                "chooser_url": "/admin/snippets/choose/wagtail_localize_test/testsnippet/",
            },
        )
        self.assertEqual(
            segments_by_content_path[f"test_streamfield.{SNIPPET_CHOOSER_BLOCK_ID}"][
                "location"
            ]["widget"],
            {
                "type": "snippet_chooser",
                "snippet_model": {
                    "app_label": "wagtail_localize_test",
                    "model_name": "nontranslatablesnippet",
                    "verbose_name": "non translatable snippet",
                    "verbose_name_plural": "non translatable snippets",
                },
                "chooser_url": "/admin/snippets/choose/wagtail_localize_test/nontranslatablesnippet/",
            },
        )

    def test_chooser_in_struct_blocks(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        CHOOSER_STRUCT_BLOCK_ID = uuid.uuid4()
        NESTED_CHOOSER_STRUCT_BLOCK_ID = uuid.uuid4()

        STREAM_DATA_WITH_CHOOSERS = [
            {
                "id": CHOOSER_STRUCT_BLOCK_ID,
                "type": "test_chooserstructblock",
                "value": {"page": self.home_page.id},
            },
            {
                "id": NESTED_CHOOSER_STRUCT_BLOCK_ID,
                "type": "test_nestedchooserstructblock",
                "value": {"nested_page": {"page": self.home_page.id}},
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA_WITH_CHOOSERS,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        chooser_path = f"test_streamfield.{CHOOSER_STRUCT_BLOCK_ID}.page"
        nested_chooser_path = (
            f"test_streamfield.{NESTED_CHOOSER_STRUCT_BLOCK_ID}.nested_page.page"
        )
        self.assertEqual(
            segments_by_content_path[chooser_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )
        self.assertEqual(
            segments_by_content_path[nested_chooser_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

    def test_choosers_in_stream_blocks(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        chooser_struct_block_id = uuid.uuid4()
        nested_chooser_struct_block_id = uuid.uuid4()
        streamblock_id = uuid.uuid4()
        nested_streamblock_chooser_block_id = uuid.uuid4()
        nested_streamblock_chooser_struct_block_id = uuid.uuid4()

        STREAM_DATA = [
            {
                "id": chooser_struct_block_id,
                "type": "test_chooserstructblock",
                "value": {"page": self.home_page.id},
            },
            {
                "id": nested_chooser_struct_block_id,
                "type": "test_nestedchooserstructblock",
                "value": {"nested_page": {"page": self.home_page.id}},
            },
            {
                "id": streamblock_id,
                "type": "test_nestedstreamblock",
                "value": [
                    {
                        "id": str(nested_streamblock_chooser_block_id),
                        "type": "chooser",
                        "value": self.home_page.id,
                    },
                    {
                        "id": str(nested_streamblock_chooser_struct_block_id),
                        "type": "chooser_in_struct",
                        "value": {"page": self.home_page.id},
                    },
                ],
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        chooser_path = f"test_streamfield.{chooser_struct_block_id}.page"
        self.assertEqual(
            segments_by_content_path[chooser_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )
        nested_chooser_path = (
            f"test_streamfield.{nested_chooser_struct_block_id}.nested_page.page"
        )
        self.assertEqual(
            segments_by_content_path[nested_chooser_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

        chooser_in_streamblock_path = (
            f"test_streamfield.{streamblock_id}.{nested_streamblock_chooser_block_id}"
        )
        self.assertEqual(
            segments_by_content_path[chooser_in_streamblock_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

        chooser_in_structblock_in_streamblock_path = f"test_streamfield.{streamblock_id}.{nested_streamblock_chooser_struct_block_id}.page"
        self.assertEqual(
            segments_by_content_path[chooser_in_structblock_in_streamblock_path][
                "location"
            ]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

    def test_choosers_in_listblock_in_stream_blocks(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        streamblock_id = uuid.uuid4()
        nested_streamblock_list_block_id = uuid.uuid4()
        list_item_id = "11111111-1111-1111-1111-111111111111"

        STREAM_DATA = [
            {
                "id": streamblock_id,
                "type": "test_nestedstreamblock",
                "value": [
                    {
                        "id": str(nested_streamblock_list_block_id),
                        "type": "chooser_in_list",
                        "value": [
                            {
                                "type": "item",
                                "value": self.home_page.id,
                                "id": list_item_id,
                            }
                        ],
                    },
                ],
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        chooser_in_listblock_in_streamblock_path = f"test_streamfield.{streamblock_id}.{nested_streamblock_list_block_id}.{list_item_id}"
        self.assertEqual(
            segments_by_content_path[chooser_in_listblock_in_streamblock_path][
                "location"
            ]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

    def test_choosers_in_structblock_in_listblock(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        # test_chooser_in_struct_in_listblock IDs
        chooser_in_struct_in_listblock_id = uuid.uuid4()
        list_item_id = "11111111-1111-1111-1111-111111111111"

        # test_chooser_in_struct_in_list_in_stream_in_listblock IDs
        chooser_in_struct_in_list_in_stream_in_listblock_id = uuid.uuid4()
        list_item_level_1 = "11111111-2222-1111-1111-111111111111"
        streamblock_id = uuid.uuid4()
        list_item_level_2 = "11111111-3333-1111-1111-111111111111"

        STREAM_DATA = [
            {
                "id": str(chooser_in_struct_in_listblock_id),
                "type": "test_chooser_in_struct_in_listblock",
                "value": [
                    {
                        "id": list_item_id,
                        "type": "item",
                        "value": {"page": self.home_page.id},
                    }
                ],
            },
            {
                "id": str(chooser_in_struct_in_list_in_stream_in_listblock_id),
                "type": "test_chooser_in_struct_in_list_in_stream_in_listblock",
                "value": [
                    {
                        "id": list_item_level_1,
                        "type": "item",
                        "value": [
                            {
                                "id": streamblock_id,
                                "type": "list",
                                "value": [
                                    {
                                        "id": list_item_level_2,
                                        "type": "item",
                                        "value": {"page": self.home_page.id},
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        chooser_in_struct_in_listblock = (
            f"test_streamfield.{chooser_in_struct_in_listblock_id}.{list_item_id}.page"
        )
        self.assertEqual(
            segments_by_content_path[chooser_in_struct_in_listblock]["location"][
                "widget"
            ],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

        chooser_in_struct_in_list_in_stream_in_listblock = (
            f"test_streamfield.{chooser_in_struct_in_list_in_stream_in_listblock_id}."
            f"{list_item_level_1}.{streamblock_id}.{list_item_level_2}.page"
        )
        self.assertEqual(
            segments_by_content_path[chooser_in_struct_in_list_in_stream_in_listblock][
                "location"
            ]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

    def test_choosers_in_listblock(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        image_chooser_in_listblock_id = uuid.uuid4()

        image_streamblock_id = uuid.uuid4()
        test_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )

        document_chooser_in_listblock_id = uuid.uuid4()
        document_streamblock_id = uuid.uuid4()
        test_document = Document.objects.create(
            title="Test document", file=get_test_image_file()
        )

        STREAM_DATA = [
            {
                "id": str(image_chooser_in_listblock_id),
                "type": "test_image_chooser_in_listblock",
                "value": [
                    {
                        "id": image_streamblock_id,
                        "type": "item",
                        "value": test_image.id,
                    },
                ],
            },
            {
                "id": str(document_chooser_in_listblock_id),
                "type": "test_document_chooser_in_listblock",
                "value": [
                    {
                        "id": document_streamblock_id,
                        "type": "item",
                        "value": test_document.id,
                    },
                ],
            },
        ]
        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        image_chooser_in_listblock = (
            f"test_streamfield.{image_chooser_in_listblock_id}.{image_streamblock_id}"
        )
        document_chooser_in_listblock = f"test_streamfield.{document_chooser_in_listblock_id}.{document_streamblock_id}"

        self.assertEqual(
            segments_by_content_path[image_chooser_in_listblock]["location"]["widget"],
            {"type": "image_chooser"},
        )
        self.assertEqual(
            segments_by_content_path[document_chooser_in_listblock]["location"][
                "widget"
            ],
            {"type": "document_chooser"},
        )

    def test_choosers_in_stream_block_in_structblock(self):
        home_page_with_specific_type = self.home_page.add_child(
            instance=TestHomePage(title="Test home page", slug="test-home-page")
        )
        self.page.test_page = self.home_page
        self.page.test_page_specific_type = home_page_with_specific_type

        struct_block_id = uuid.uuid4()
        nested_streamblock_chooser_block_id = uuid.uuid4()
        nested_streamblock_chooser_struct_block_id = uuid.uuid4()

        STREAM_DATA = [
            {
                "id": str(struct_block_id),
                "type": "test_streamblock_in_structblock",
                "value": {
                    "nested_stream": [
                        {
                            "id": str(nested_streamblock_chooser_block_id),
                            "type": "page",
                            "value": self.home_page.id,
                        },
                        {
                            "id": str(nested_streamblock_chooser_struct_block_id),
                            "type": "checklist",
                            "value": {"page": self.home_page.id},
                        },
                    ]
                },
            },
        ]

        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block,
            STREAM_DATA,
            is_lazy=True,
        )
        self.page.save()

        # Update source
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        segments_by_content_path = {
            segment["contentPath"]: segment
            for segment in props["segments"]
            if segment["contentPath"].startswith("test_streamfield")
        }

        chooser_in_streamblock_path = f"test_streamfield.{struct_block_id}.nested_stream.{nested_streamblock_chooser_block_id}"
        self.assertEqual(
            segments_by_content_path[chooser_in_streamblock_path]["location"]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

        chooser_in_structblock_in_streamblock_path = f"test_streamfield.{struct_block_id}.nested_stream.{nested_streamblock_chooser_struct_block_id}.page"
        self.assertEqual(
            segments_by_content_path[chooser_in_structblock_in_streamblock_path][
                "location"
            ]["widget"],
            {"type": "page_chooser", "allowed_page_types": ["wagtailcore.page"]},
        )

    def test_manually_translated_related_object(self):
        # Related objects don't have to be translated by Wagtail localize so test with the snippet's translation record deleted
        self.snippet_translation.delete()

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        props = json.loads(response.context["props"])

        # Check related object
        related_object_segment = props["segments"][18]
        self.assertEqual(related_object_segment["type"], "related_object")
        self.assertEqual(related_object_segment["contentPath"], "test_snippet")
        self.assertEqual(
            related_object_segment["location"],
            {
                "tab": "content",
                "field": "Test snippet",
                "blockId": None,
                "fieldHelpText": "",
                "order": 8,
                "subField": None,
                "widget": None,
            },
        )
        self.assertEqual(related_object_segment["source"]["title"], str(self.snippet))
        self.assertEqual(related_object_segment["dest"]["title"], str(self.fr_snippet))
        self.assertIsNone(related_object_segment["translationProgress"])

    def test_override_types(self):
        # Similar to above but adds some more overridable things to test with
        self.page.test_synchronized_image = Image.objects.create(
            title="Test image", file=get_test_image_file()
        )
        self.page.test_synchronized_document = Document.objects.create(
            title="Test document", file=get_test_image_file()
        )
        self.page.test_synchronized_snippet = self.snippet

        url_block_id = uuid.uuid4()
        page_block_id = uuid.uuid4()
        image_block_id = uuid.uuid4()
        document_block_id = uuid.uuid4()
        snippet_block_id = uuid.uuid4()
        stream_data = [
            {
                "id": str(url_block_id),
                "type": "test_urlblock",
                "value": "https://wagtail.org/",
            },
            {
                "id": str(page_block_id),
                "type": "test_pagechooserblock",
                "value": self.page.id,
            },
            {
                "id": str(image_block_id),
                "type": "test_imagechooserblock",
                "value": self.page.test_synchronized_image.id,
            },
            {
                "id": str(document_block_id),
                "type": "test_documentchooserblock",
                "value": self.page.test_synchronized_document.id,
            },
            {
                "id": str(snippet_block_id),
                "type": "test_snippetchooserblock",
                "value": self.snippet.id,
            },
        ]

        self.page.test_streamfield = TestPage.test_streamfield.field.to_python(
            json.dumps(stream_data)
        )

        self.page.save_revision().publish()
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            [
                (
                    segment["contentPath"],
                    segment["location"]["widget"],
                    segment["value"],
                )
                for segment in props["segments"]
                if segment["type"] == "synchronised_value"
            ],
            [
                (
                    "test_richtextfield.'http://example.com'",
                    {"type": "text"},
                    "http://example.com",
                ),
                (
                    f"test_streamfield.{url_block_id}",
                    {"type": "text"},
                    "https://wagtail.org/",
                ),
                (
                    f"test_streamfield.{page_block_id}",
                    {
                        "type": "page_chooser",
                        "allowed_page_types": ["wagtailcore.page"],
                    },
                    self.page.id,
                ),
                (
                    f"test_streamfield.{image_block_id}",
                    {"type": "image_chooser"},
                    self.page.test_synchronized_image.id,
                ),
                (
                    f"test_streamfield.{document_block_id}",
                    {"type": "document_chooser"},
                    self.page.test_synchronized_document.id,
                ),
                ("test_synchronized_emailfield", {"type": "text"}, "email@example.com"),
                (
                    "test_synchronized_image",
                    {"type": "image_chooser"},
                    self.page.test_synchronized_image.id,
                ),
                (
                    "test_synchronized_document",
                    {"type": "document_chooser"},
                    self.page.test_synchronized_document.id,
                ),
                (
                    "test_synchronized_snippet",
                    {
                        "type": "snippet_chooser",
                        "snippet_model": {
                            "app_label": "wagtail_localize_test",
                            "model_name": "testsnippet",
                            "verbose_name": "test snippet",
                            "verbose_name_plural": "test snippets",
                        },
                        "chooser_url": "/admin/snippets/choose/wagtail_localize_test/testsnippet/",
                    },
                    self.snippet.id,
                ),
            ],
        )

    def test_edit_page_translation_with_custom_edit_handler(self):
        page = self.home_page.add_child(
            instance=PageWithCustomEditHandler(
                title="Custom edit handler",
                foo_field="Foo",
                bar_field="Bar",
                baz_field="Baz",
                child_objects=[
                    PageWithCustomEditHandlerChildObject(
                        field="Test 1",
                    ),
                    PageWithCustomEditHandlerChildObject(
                        field="Test 2",
                    ),
                ],
            )
        )

        source, created = TranslationSource.get_or_create_from_instance(page)
        translation = Translation.objects.create(
            source=source,
            target_locale=self.fr_locale,
        )
        translation.save_target()
        fr_page = page.get_translation(self.fr_locale)

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[fr_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            props["tabs"],
            [
                {"label": "Bar", "slug": "bar"},
                {"label": "Child objects", "slug": "child-objects"},
                {"label": "Foo", "slug": "foo"},
                {"label": "Content", "slug": "content"},
                {"label": "Promote", "slug": "promote"},
                {"label": "Settings", "slug": "settings"},
            ],
        )

        # Test locations
        locations = [
            {
                "value": segment["source"],
                "tab": segment["location"]["tab"],
                "field": segment["location"]["field"],
                "model_order": segment["order"],
                "panel_order": segment["location"]["order"],
            }
            for segment in props["segments"]
        ]
        self.assertEqual(
            locations,
            [
                {
                    "value": "Bar",
                    "tab": "bar",
                    "field": "Bar field",
                    "model_order": 4,
                    "panel_order": 0,
                },
                {
                    "value": "Baz",
                    "tab": "bar",
                    "field": "Baz field",
                    "model_order": 5,
                    "panel_order": 1,
                },
                {
                    "value": "Test 1",
                    "tab": "child-objects",
                    "field": "Page with custom edit handler child object",
                    "model_order": 6,
                    "panel_order": 2,
                },
                {
                    "value": "Test 2",
                    "tab": "child-objects",
                    "field": "Page with custom edit handler child object",
                    "model_order": 7,
                    "panel_order": 2,
                },
                {
                    "value": "Foo",
                    "tab": "foo",
                    "field": "Foo field",
                    "model_order": 3,
                    "panel_order": 3,
                },
                {
                    "value": "Custom edit handler",
                    "tab": "content",
                    "field": "Title",
                    "model_order": 1,
                    "panel_order": 4,
                },
                {
                    "value": "custom-edit-handler",
                    "tab": "promote",
                    "field": "Slug",
                    "model_order": 2,
                    "panel_order": 5,
                },
            ],
        )

    def test_edit_page_translation_with_multi_mode_preview(self):
        # Add some extra preview modes to the page
        previous_preview_modes = TestPage.preview_modes
        TestPage.preview_modes = [
            ("", gettext_lazy("Default")),
            ("first-mode", gettext_lazy("First mode")),
            ("second-mode", gettext_lazy("Second mode")),
        ]

        try:
            response = self.client.get(
                reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
            )
        finally:
            TestPage.preview_modes = previous_preview_modes

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            props["previewModes"],
            [
                {
                    "mode": "",
                    "label": "Default",
                    "url": reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.page_translation.id],
                    ),
                },
                {
                    "mode": "first-mode",
                    "label": "First mode",
                    "url": reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.page_translation.id, "first-mode"],
                    ),
                },
                {
                    "mode": "second-mode",
                    "label": "Second mode",
                    "url": reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.page_translation.id, "second-mode"],
                    ),
                },
            ],
        )

    def test_cant_edit_page_translation_without_perms(self):
        self.moderators_group.page_permissions.all().delete()
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        assert_permission_denied(self, response)

    def test_edit_page_translation_with_missing_panel(self):
        # Hide fields that don't have a panel to edit them with
        previous_panels = TestPage.content_panels
        TestPage.content_panels = [
            TitleFieldPanel("title"),
            FieldPanel("test_textfield"),
        ]
        TestPage.get_edit_handler.cache_clear()

        try:
            response = self.client.get(
                reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
            )
        finally:
            TestPage.content_panels = previous_panels
            TestPage.get_edit_handler.cache_clear()

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            props["tabs"],
            [
                {"label": "Content", "slug": "content"},
                {"label": "Promote", "slug": "promote"},
                {"label": "Settings", "slug": "settings"},
            ],
        )

        # Test locations
        locations = [
            {
                "value": segment["source"],
                "tab": segment["location"]["tab"],
                "field": segment["location"]["field"],
                "model_order": segment["order"],
                "panel_order": segment["location"]["order"],
            }
            for segment in props["segments"]
        ]
        self.assertEqual(
            locations,
            [
                {
                    "value": "A text field",
                    "tab": "content",
                    "field": "Test textfield",
                    "model_order": 2,
                    "panel_order": 1,
                },
            ],
        )

    def test_edit_page_from_outdated_translation_source(self):
        # note: we reset test app migrations on a regular basis, so
        # this sets a stub initial schema version.
        self.page_source.schema_version = "0001_initial_stub"
        self.page_source.save()

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.assertContains(
            response,
            "The data model for &#x27;Test page&#x27; has been changed since the last translation sync. "
            "If any new fields have been added recently, these may not be visible until the next translation sync.",
        )

    def test_edit_snippet_translation(self):
        response = self.client.get(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            props["object"]["title"], f"TestSnippet object ({self.fr_snippet.id})"
        )
        self.assertFalse(
            props["object"]["isLive"]
        )  # Draftable snippet is saved as draft
        self.assertIsNone(
            props["object"]["lastPublishedDate"]
        )  # and so it won't have a last published date initially
        self.assertFalse(props["object"]["isLocked"])

        # Snippets don't have live URL, breadcrumb, or tabs
        self.assertIsNone(props["object"]["liveUrl"])
        self.assertEqual(props["breadcrumb"], [])
        self.assertEqual(props["tabs"], [{"label": "Content", "slug": "content"}])

        self.assertEqual(
            props["sourceLocale"], {"code": "en", "displayName": "English"}
        )
        self.assertEqual(props["locale"], {"code": "fr", "displayName": "French"})

        self.assertEqual(
            props["translations"],
            [
                {
                    "title": f"TestSnippet object ({self.snippet.id})",
                    "locale": {"code": "en", "displayName": "English"},
                    "editUrl": reverse(
                        f"wagtailsnippets_{self.snippet._meta.app_label}_{self.snippet._meta.model_name}:edit",
                        args=[quote(self.snippet.pk)],
                    ),
                }
            ],
        )

        self.assertTrue(props["perms"]["canPublish"])
        self.assertFalse(props["perms"]["canUnpublish"])
        self.assertFalse(props["perms"]["canLock"])
        self.assertFalse(props["perms"]["canUnlock"])
        self.assertTrue(props["perms"]["canDelete"])

        self.assertIsNone(props["links"]["unpublishUrl"])
        self.assertIsNone(props["links"]["lockUrl"])
        self.assertIsNone(props["links"]["unlockUrl"])
        self.assertEqual(
            props["links"]["deleteUrl"],
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:delete",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        self.assertEqual(props["previewModes"], [])

        self.assertEqual(props["initialStringTranslations"], [])

        # Check segments
        self.assertEqual(
            [
                (segment["contentPath"], segment["source"])
                for segment in props["segments"]
            ],
            [
                ("field", "Test snippet"),
            ],
        )

        # Test locations
        self.assertEqual(
            props["segments"][0]["location"],
            {
                "tab": "",
                "field": "Field",
                "blockId": None,
                "fieldHelpText": "",
                "order": 0,
                "subField": None,
                "widget": None,
            },
        )

    def test_cant_edit_snippet_translation_without_perms(self):
        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()
        response = self.client.get(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            )
        )

        assert_permission_denied(self, response)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")
        self.assertEqual(
            messages[0].message,
            "Sorry, you do not have permission to access this area.\n\n\n\n\n",
        )

    def test_edit_nested_snippet_translation(self):
        for permission in Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(Header)
        ):
            self.moderators_group.permissions.add(permission)

        snippet = Header.objects.create(name="Test header snippet")
        nav_link = NavigationLink(label="Nav", page=self.page)
        nav_link.sub_navigation_links = [
            SubNavigationLink(label="SubNav", page=self.home_page)
        ]
        snippet.navigation_links = [nav_link]
        snippet.save()

        snippet_source, created = TranslationSource.get_or_create_from_instance(snippet)
        snippet_translation = Translation.objects.create(
            source=snippet_source,
            target_locale=self.fr_locale,
        )
        snippet_translation.save_target()
        fr_snippet = snippet.get_translation(self.fr_locale)

        response = self.client.get(
            reverse(
                f"wagtailsnippets_{fr_snippet._meta.app_label}_{fr_snippet._meta.model_name}:edit",
                args=[quote(fr_snippet.pk)],
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_translation_when_block_deleted_from_source_page(self):
        # Tests for #433 - If a streamfield block that contained translatable text was deleted
        # from the source page after submission, the translation editor would crash.

        # Remove all blocks from source page
        self.page.test_streamfield = StreamValue(
            TestPage.test_streamfield.field.stream_block, [], is_lazy=True
        )
        self.page.save_revision().publish()

        # Just testing that it doesn't crash
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_page_translation_from_translated_page_show_convert_to_alias_button(
        self,
    ):
        de_locale = Locale.objects.create(language_code="de")
        self.client.post(
            reverse(
                "wagtail_localize:submit_page_translation",
                args=[self.fr_page.id],
            ),
            {"locales": [de_locale.id]},
        )
        de_page = self.fr_page.get_translation(de_locale)
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[de_page.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translation.html"
        )

        # Check props
        props = json.loads(response.context["props"])

        self.assertEqual(
            props["links"]["convertToAliasUrl"],
            reverse("wagtail_localize:convert_to_alias", args=[de_page.id]),
        )


@freeze_time("2020-08-21")
class TestPublishTranslation(EditTranslationTestData, APITestCase):
    def test_publish_page_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Un champ de caractères",
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        # Fill all the remaining fields so that we don't get a warning message
        string_segments = self.page_translation.source.stringsegment_set.all().order_by(
            "order"
        )
        for segment in string_segments.annotate_translation(self.fr_locale).filter(
            translation__isnull=True
        ):
            StringTranslation.objects.create(
                translation_of=segment.string,
                context=segment.context,
                locale=self.fr_locale,
                data=segment.string.data,
                translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
            )

        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")

        self.assertEqual(
            messages[0].message,
            "Published &#x27;The title&#x27; in French.\n\n\n\n\n",
        )

        # Check the page was published
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, "Un champ de caractères")
        latest_revision = self.fr_page.get_latest_revision()
        self.assertEqual(latest_revision.user, self.user)

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.revision, latest_revision)

    def test_publish_page_translation_with_missing_translations(self):
        # Same as the above test except we only fill in one field. We should be given a warning but the publish should be published.
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Un champ de caractères",
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Check warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "warning")

        self.assertEqual(
            messages[0].message,
            "Published &#x27;The title&#x27; in French with missing translations - see below.\n\n\n\n\n",
        )

        # Check the page was published
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, "Un champ de caractères")
        latest_revision = self.fr_page.get_latest_revision()
        self.assertEqual(latest_revision.user, self.user)

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.revision, latest_revision)

    def test_publish_page_translation_with_new_field_error(self):
        translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data=(
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation."
            ),
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")

        self.assertEqual(
            messages[0].message,
            "New validation errors were found when publishing &#x27;The title&#x27; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n",
        )

        # Check that the test_charfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, "A char field")

        # Check specific error was added to the translation
        translation.refresh_from_db()
        self.assertTrue(translation.has_error)
        self.assertEqual(
            translation.get_error(),
            "Ensure this value has at most 255 characters (it has 329).",
        )

        # Check page was not published
        self.assertFalse(TranslationLog.objects.exists())

    def test_publish_page_translation_with_known_field_error(self):
        # Same as previous test, except the error is already known at the point of publishing the page. So the page is published
        # but the invalid field is ignored.
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data=(
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation. "
                "This value is way too long for a char field so it should fail to publish and add an error to the translation."
            ),
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
            has_error=True,
            field_error="Ensure this value has at most 255 characters (it has 329).",
        )

        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Check warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "warning")

        self.assertEqual(
            messages[0].message,
            "Published &#x27;The title&#x27; in French with missing translations - see below.\n\n\n\n\n",
        )

        # Check that the test_charfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, "A char field")

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.revision, self.fr_page.get_latest_revision())

    def test_publish_page_translation_with_invalid_segment_override(self):
        # Set the email address override to something invalid
        self.segment_override.data_json = '"Definitely not an email address"'
        self.segment_override.save()

        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")

        self.assertEqual(
            messages[0].message,
            "New validation errors were found when publishing &#x27;The title&#x27; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n",
        )

        # Check that the test_synchronized_emailfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_synchronized_emailfield, "email@example.com")

        # Check specific error was added to the override
        self.segment_override.refresh_from_db()
        self.assertTrue(self.segment_override.has_error)
        self.assertEqual(
            self.segment_override.get_error(), "Enter a valid email address."
        )

        # Check page was not published
        self.assertFalse(TranslationLog.objects.exists())

    def test_cant_publish_page_translation_without_perms(self):
        self.moderators_group.page_permissions.filter(
            permission__codename="publish_page"
        ).delete()
        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "action": "publish",
            },
        )
        assert_permission_denied(self, response)

    def test_publish_snippet_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="Test snippet"),
            context=TranslationContext.objects.get(path="field"),
            locale=self.fr_locale,
            data="Extrait de test",
        )

        response = self.client.post(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
            {
                "action": "publish",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")

        self.assertEqual(
            messages[0].message,
            f"Published &#x27;TestSnippet object ({self.fr_snippet.id})&#x27; in French.\n\n\n\n\n",
        )

        # Check the snippet was published
        self.fr_snippet.refresh_from_db()
        self.assertEqual(self.fr_snippet.field, "Extrait de test")

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.snippet_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertIsInstance(log.revision, Revision)

    def test_cant_publish_snippet_translation_without_perms(self):
        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()

        response = self.client.post(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
            {
                "action": "publish",
            },
        )

        assert_permission_denied(self, response)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")
        self.assertEqual(
            messages[0].message,
            "Sorry, you do not have permission to access this area.\n\n\n\n\n",
        )


class TestPreviewTranslationView(EditTranslationTestData, TestCase):
    def test_preview_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Un champ de caractères",
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        response = self.client.get(
            reverse(
                "wagtail_localize:preview_translation", args=[self.page_translation.id]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TestPage.template)
        self.assertContains(response, "Un champ de caractères")


class TestStopTranslationView(EditTranslationTestData, TestCase):
    def test_stop_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:stop_translation", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.page_translation.refresh_from_db()
        self.assertFalse(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")
        self.assertEqual(messages[0].message, "Translation has been stopped.\n\n\n\n\n")

    def test_stop_translation_without_next_url(self):
        # You should always call this view with a next URL. But if you forget, it should redirect to the dashboard.

        response = self.client.post(
            reverse(
                "wagtail_localize:stop_translation", args=[self.page_translation.id]
            )
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))

        self.page_translation.refresh_from_db()
        self.assertFalse(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")
        self.assertEqual(messages[0].message, "Translation has been stopped.\n\n\n\n\n")


class TestRestartTranslation(EditTranslationTestData, TestCase):
    def test_restart_page_translation(self):
        self.page_translation.enabled = False
        self.page_translation.save()
        response = self.client.post(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            {
                "localize-restart-translation": "yes",
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.page_translation.refresh_from_db()
        self.assertTrue(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")
        self.assertEqual(
            messages[0].message, "Translation has been restarted.\n\n\n\n\n"
        )

    def test_restart_snippet_translation(self):
        self.snippet_translation.enabled = False
        self.snippet_translation.save()
        response = self.client.post(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
            {
                "localize-restart-translation": "yes",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        self.snippet_translation.refresh_from_db()
        self.assertTrue(self.snippet_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "success")
        self.assertEqual(
            messages[0].message, "Translation has been restarted.\n\n\n\n\n"
        )


class TestRestartTranslationButton(EditTranslationTestData, TestCase):
    def test_page(self):
        self.page_translation.enabled = False
        self.page_translation.save()

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.assertContains(response, "Start Synced translation")

    def test_doesnt_show_when_no_translation_for_page(self):
        self.page_translation.delete()

        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        self.assertNotContains(response, "Start Synced translation")

    def test_snippet(self):
        self.snippet_translation.enabled = False
        self.snippet_translation.save()

        response = self.client.get(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            )
        )

        self.assertContains(response, "Start Synced translation")

    def test_doesnt_show_when_no_translation_for_snippet(self):
        self.snippet_translation.delete()

        response = self.client.get(
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            )
        )

        self.assertNotContains(response, "Start Synced translation")

    def test_doesnt_show_on_create_for_snippet(self):
        response = self.client.get(
            reverse(
                f"wagtailsnippets_{TestSnippet._meta.app_label}_{TestSnippet._meta.model_name}:add"
            )
        )
        self.assertNotContains(response, "Start Synced translation")

    def test_doesnt_show_for_untranslatable_snippet(self):
        snippet = NonTranslatableSnippet.objects.create(field="Test")
        response = self.client.get(
            reverse(
                f"wagtailsnippets_{snippet._meta.app_label}_{snippet._meta.model_name}:edit",
                args=[quote(snippet.pk)],
            )
        )
        self.assertNotContains(response, "Start Synced translation")


@freeze_time("2020-08-21")
class TestEditStringTranslationAPIView(EditTranslationTestData, APITestCase):
    def test_create_string_translation(self):
        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            {
                "value": "Un champ de caractères",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "string_id": string.id,
                "segment_id": string_segment.id,
                "data": "Un champ de caractères",
                "error": None,
                "comment": "Translated manually on 21 August 2020",
                "last_translated_by": {
                    "avatar_url": self.avatar_url,
                    "full_name": "",
                },
            },
        )

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_update_string_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Not translated!",
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE,
        )

        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            {
                "value": "Un champ de caractères",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "string_id": string.id,
                "segment_id": string_segment.id,
                "data": "Un champ de caractères",
                "error": None,
                "comment": "Translated manually on 21 August 2020",
                "last_translated_by": {
                    "avatar_url": self.avatar_url,
                    "full_name": "",
                },
            },
        )

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_update_string_translation_with_bad_html(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Not translated!",
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE,
        )

        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            {
                "value": "Un champ de caractères <script>Some nasty JS</script>",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "string_id": string.id,
                "segment_id": string_segment.id,
                "data": "Un champ de caractères <script>Some nasty JS</script>",
                "error": "<script> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)",
                "comment": "Translated manually on 21 August 2020",
                "last_translated_by": {
                    "avatar_url": self.avatar_url,
                    "full_name": "",
                },
            },
        )

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)
        self.assertTrue(translation.has_error)

    def test_update_string_translation_with_unkown_links(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Not translated!",
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE,
        )

        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            {
                "value": 'Tiens, <a id="a42">un nouveau lien</a>',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "string_id": string.id,
                "segment_id": string_segment.id,
                "data": 'Tiens, <a id="a42">un nouveau lien</a>',
                "error": "Unrecognised id found in an <a> tag: a42",
                "comment": "Translated manually on 21 August 2020",
                "last_translated_by": {
                    "avatar_url": self.avatar_url,
                    "full_name": "",
                },
            },
        )

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)
        self.assertTrue(translation.has_error)

    def test_delete_string_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Not translated!",
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE,
        )

        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.delete(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            )
        )

        # Response should contain the deleted string
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "string_id": string.id,
                "segment_id": string_segment.id,
                "data": "Not translated!",
                "error": None,
                "comment": "Machine translated on 21 August 2020",
                "last_translated_by": None,
            },
        )

        self.assertFalse(StringTranslation.objects.exists())

    def test_delete_non_existent_string_translation(self):
        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        response = self.client.delete(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_cant_edit_translation_without_page_perms(self):
        string = String.objects.get(data="A char field")
        string_segment = string.segments.get()

        self.moderators_group.page_permissions.all().delete()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.page_translation.id, string_segment.id],
            ),
            {
                "value": "Un champ de caractères",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_cant_edit_translation_without_snippet_perms(self):
        string = String.objects.get(data="Test snippet")
        string_segment = string.segments.get()

        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_string_translation",
                args=[self.snippet_translation.id, string_segment.id],
            ),
            {
                "value": "Un champ de caractères",
            },
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
            ]
        }
    )
    def test_edit_translation_with_drf_default_permissions_classes(self):
        self.assertEqual(
            api_settings.DEFAULT_PERMISSION_CLASSES,
            [DjangoModelPermissionsOrAnonReadOnly],
        )
        self.assertEqual(
            edit_string_translation.view_class.permission_classes, [IsAuthenticated]
        )

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework.authentication.TokenAuthentication"
            ]
        }
    )
    def test_update_override_with_drf_default_authentication_classes(self):
        self.assertEqual(
            api_settings.DEFAULT_AUTHENTICATION_CLASSES,
            [TokenAuthentication],
        )
        self.assertEqual(
            edit_string_translation.view_class.authentication_classes,
            [SessionAuthentication],
        )


@freeze_time("2020-08-21")
class TestEditOverrideAPIView(EditTranslationTestData, APITestCase):
    def test_create_override(self):
        self.segment_override.delete()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            ),
            {
                "value": "overridden_by_view@example.com",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "segment_id": self.overridable_segment.id,
                "error": None,
                "data": "overridden_by_view@example.com",
            },
        )

        override = SegmentOverride.objects.get()
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"overridden_by_view@example.com"')

    def test_update_override(self):
        response = self.client.put(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            ),
            {
                "value": "updated_by_view@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "segment_id": self.overridable_segment.id,
                "error": None,
                "data": "updated_by_view@example.com",
            },
        )

        override = SegmentOverride.objects.get()
        self.assertEqual(override.id, self.segment_override.id)
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"updated_by_view@example.com"')

    def test_update_override_with_invalid_value(self):
        # Overrides are not currently validated on save.
        # But they are validated when the page/snippet is published.
        # TODO (someday): Would be nice to have the validation here
        response = self.client.put(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            ),
            {
                "value": "Definitely not an email address",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "segment_id": self.overridable_segment.id,
                "error": None,
                "data": "Definitely not an email address",
            },
        )

        override = SegmentOverride.objects.get()
        self.assertEqual(override.id, self.segment_override.id)
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"Definitely not an email address"')

    def test_delete_override(self):
        response = self.client.delete(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {
                "segment_id": self.overridable_segment.id,
                "error": None,
                "data": "overridden@example.com",
            },
        )

        self.assertFalse(SegmentOverride.objects.exists())

    def test_delete_non_existent_override(self):
        self.segment_override.delete()

        response = self.client.delete(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_cant_edit_overrides_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()

        response = self.client.put(
            reverse(
                "wagtail_localize:edit_override",
                args=[self.page_translation.id, self.overridable_segment.id],
            ),
            {
                "value": "updated_by_view@example.com",
            },
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
            ]
        }
    )
    def test_update_override_with_drf_default_permissions_classes(self):
        self.assertEqual(
            api_settings.DEFAULT_PERMISSION_CLASSES,
            [DjangoModelPermissionsOrAnonReadOnly],
        )
        self.assertEqual(edit_override.view_class.permission_classes, [IsAuthenticated])

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework.authentication.TokenAuthentication"
            ]
        }
    )
    def test_update_override_with_drf_default_authentication_classes(self):
        self.assertEqual(
            api_settings.DEFAULT_AUTHENTICATION_CLASSES,
            [TokenAuthentication],
        )
        self.assertEqual(
            edit_override.view_class.authentication_classes, [SessionAuthentication]
        )


class TestDownloadPOFileView(EditTranslationTestData, TestCase):
    def test_download_pofile_page(self):
        response = self.client.get(
            reverse("wagtail_localize:download_pofile", args=[self.page_translation.id])
        )

        self.assertContains(
            response,
            f"X-WagtailLocalize-TranslationID: {str(self.page_translation.uuid)}",
        )
        self.assertContains(
            response, 'msgctxt "test_charfield"\nmsgid "A char field"\nmsgstr ""'
        )
        self.assertContains(
            response, 'msgctxt "test_textfield"\nmsgid "A text field"\nmsgstr ""'
        )
        self.assertContains(
            response, 'msgctxt "test_emailfield"\nmsgid "email@example.com"\nmsgstr ""'
        )
        self.assertContains(
            response, 'msgctxt "test_slugfield"\nmsgid "a-slug-field"\nmsgstr ""'
        )
        self.assertContains(
            response,
            'msgctxt "test_urlfield"\nmsgid "https://www.example.com"\nmsgstr ""',
        )
        self.assertContains(
            response,
            'msgctxt "test_richtextfield"\nmsgid "This is a heading"\nmsgstr ""',
        )
        self.assertContains(
            response,
            'msgctxt "test_richtextfield"\nmsgid "This is a paragraph. &lt;foo&gt; <b>Bold text</b>"\nmsgstr ""',
        )
        self.assertContains(
            response,
            'msgctxt "test_richtextfield"\nmsgid "<a id=\\"a1\\">This is a link</a>."\nmsgstr ""',
        )
        self.assertContains(
            response,
            'msgctxt "test_richtextfield"\nmsgid "Special characters: \'\\"!? セキレイ"\nmsgstr ""',
        )
        self.assertContains(
            response,
            f'msgctxt "test_streamfield.{STREAM_TEXT_BLOCK_ID}"\nmsgid "This is a text block"\nmsgstr ""',
        )

    def test_download_pofile_snippet(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:download_pofile", args=[self.snippet_translation.id]
            )
        )

        self.assertContains(
            response,
            f"X-WagtailLocalize-TranslationID: {str(self.snippet_translation.uuid)}",
        )
        self.assertContains(
            response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr ""'
        )

    def test_includes_existing_translations(self):
        string = String.objects.get(data="Test snippet")
        context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=string,
            context=context,
            locale=self.fr_locale,
            data="Extrait de test",
        )

        response = self.client.get(
            reverse(
                "wagtail_localize:download_pofile", args=[self.snippet_translation.id]
            )
        )
        self.assertContains(
            response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr "Extrait de test"'
        )

    def test_includes_obsolete_translations(self):
        string = String.objects.create(
            locale=Locale.objects.get(language_code="en"),
            data="A string that is no longer used on the snippet",
        )
        context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=string,
            context=context,
            locale=self.fr_locale,
            data="Une chaîne qui n'est plus utilisée sur l'extrait",
        )

        response = self.client.get(
            reverse(
                "wagtail_localize:download_pofile", args=[self.snippet_translation.id]
            )
        )

        self.assertContains(
            response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr ""'
        )
        self.assertContains(
            response,
            'msgctxt "field"\n#~ msgid "A string that is no longer used on the snippet"\n#~ msgstr "Une chaîne qui n\'est plus utilisée sur l\'extrait"',
        )

    def test_cant_download_pofile_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()
        response = self.client.get(
            reverse("wagtail_localize:download_pofile", args=[self.page_translation.id])
        )
        assert_permission_denied(self, response)

    def test_cant_download_pofile_without_snippet_perms(self):
        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()
        response = self.client.get(
            reverse(
                "wagtail_localize:download_pofile", args=[self.snippet_translation.id]
            )
        )
        assert_permission_denied(self, response)


class TestUploadPOFileView(EditTranslationTestData, TestCase):
    def test_upload_pofile_page(self):
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="A char field",
                msgctxt="test_charfield",
                msgstr="Un champ de caractères",
            )
        )

        po.append(
            polib.POEntry(
                msgid='<a id="a1">This is a link</a>.',
                msgctxt="test_richtextfield",
                msgstr='<a id="a1">Ceci est un lien</a>.',
            )
        )

        po.append(
            polib.POEntry(
                msgid="Special characters: '\"!? セキレイ",
                msgctxt="test_richtextfield",
                msgstr="Caractères spéciaux: '\"!? セキレイ",
            )
        )

        response = self.client.post(
            reverse("wagtail_localize:upload_pofile", args=[self.page_translation.id]),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        translation_1 = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, "Un champ de caractères")
        self.assertEqual(
            translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation_1.tool_name, "PO File")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '<a id="a1">Ceci est un lien</a>.')
        self.assertEqual(
            translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation_2.tool_name, "PO File")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data="Special characters: '\"!? セキレイ",
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, "Caractères spéciaux: '\"!? セキレイ")
        self.assertEqual(
            translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation_3.tool_name, "PO File")
        self.assertEqual(translation_3.last_translated_by, self.user)

    def test_upload_pofile_snippet(self):
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.snippet_translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="Test snippet",
                msgctxt="field",
                msgstr="Extrait de test",
            )
        )

        response = self.client.post(
            reverse(
                "wagtail_localize:upload_pofile", args=[self.snippet_translation.id]
            ),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        translation = StringTranslation.objects.get(
            translation_of__data="Test snippet",
            context__path="field",
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, "Extrait de test")
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "PO File")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_upload_pofile_page_without_strings(self):
        # You can leave strings out, this shouldn't affect existing translations

        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Un champ de caractères",
        )

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        response = self.client.post(
            reverse("wagtail_localize:upload_pofile", args=[self.page_translation.id]),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Existing translation should be uneffected
        translation = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, "Un champ de caractères")
        self.assertEqual(translation.translation_type, "")
        self.assertEqual(translation.tool_name, "")
        self.assertIsNone(translation.last_translated_by)

    def test_upload_pofile_page_without_next_url(self):
        # You should always call this view with a next URL. But if you forget, it should redirect to the dashboard.

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        response = self.client.post(
            reverse("wagtail_localize:upload_pofile", args=[self.page_translation.id]),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
            },
        )

        self.assertRedirects(response, reverse("wagtailadmin_home"))

    def test_upload_pofile_page_with_unknown_strings(self):
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        # Source string not recognised
        po.append(
            polib.POEntry(
                msgid="A tweaked char field",
                msgctxt="test_charfield",
                msgstr="Un champ de caractères",
            )
        )

        # Context not recognised
        po.append(
            polib.POEntry(
                msgid="A char field",
                msgctxt="test_charfield_badcontext",
                msgstr="Un champ de caractères",
            )
        )

        # Uploaded against wrong object
        po.append(
            polib.POEntry(
                msgid="Test snippet",
                msgctxt="field",
                msgstr="Extrait de test",
            )
        )

        response = self.client.post(
            reverse("wagtail_localize:upload_pofile", args=[self.page_translation.id]),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Neither string should be imported
        self.assertFalse(StringTranslation.objects.exists())

    def test_upload_pofile_snippet_invalid_file(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:upload_pofile", args=[self.snippet_translation.id]
            ),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    b"Foo",
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")
        self.assertEqual(
            messages[0].message, "Please upload a valid PO file.\n\n\n\n\n"
        )

        # Nothing should be imported
        self.assertFalse(StringTranslation.objects.exists())

    def test_upload_pofile_snippet_filename_instead_of_file(self):
        # POLib checks if the string passed to it is a file before parsing.So always pass
        # it a file so that users can't upload filenames and read data off the disk.
        # This test makes sure that filenames are treated as an error, even if there is a
        # valid file there.

        # It's very easy to make this test fail by changing the view to parse the incoming
        # string directly without using a temporary file.

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.snippet_translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="Test snippet",
                msgctxt="field",
                msgstr="Extrait de test",
            )
        )

        with tempfile.NamedTemporaryFile() as f:
            f.write(str(po).encode("utf-8"))
            f.flush()

            response = self.client.post(
                reverse(
                    "wagtail_localize:upload_pofile", args=[self.snippet_translation.id]
                ),
                {
                    "file": SimpleUploadedFile(
                        "translations.po",
                        f.name.encode("utf-8"),
                        content_type="text/x-gettext-translation",
                    ),
                    "next": reverse(
                        f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                        args=[quote(self.fr_snippet.pk)],
                    ),
                },
            )

            self.assertRedirects(
                response,
                reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            )

            # User should be warned with a message
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(messages[0].level_tag, "error")
            self.assertEqual(
                messages[0].message, "Please upload a valid PO file.\n\n\n\n\n"
            )

            # Nothing should be imported
            self.assertFalse(StringTranslation.objects.exists())

    def test_upload_pofile_snippet_against_wrong_translationid(self):
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        po.append(
            polib.POEntry(
                msgid="Test snippet",
                msgctxt="field",
                msgstr="Extrait de test",
            )
        )

        response = self.client.post(
            reverse(
                "wagtail_localize:upload_pofile", args=[self.snippet_translation.id]
            ),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")
        self.assertEqual(
            messages[0].message,
            "Cannot import PO file that was created for a different translation.\n\n\n\n\n",
        )

        # Nothing should be imported
        self.assertFalse(StringTranslation.objects.exists())

    def test_cant_upload_pofile_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        response = self.client.post(
            reverse("wagtail_localize:upload_pofile", args=[self.page_translation.id]),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        assert_permission_denied(self, response)

    def test_cant_upload_pofile_without_snippet_perms(self):
        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.snippet_translation.uuid),
        }

        response = self.client.post(
            reverse(
                "wagtail_localize:upload_pofile", args=[self.snippet_translation.id]
            ),
            {
                "file": SimpleUploadedFile(
                    "translations.po",
                    str(po).encode("utf-8"),
                    content_type="text/x-gettext-translation",
                ),
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        assert_permission_denied(self, response)


class TestMachineTranslateView(EditTranslationTestData, TestCase):
    def test_machine_translate_page(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        translation_1 = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, "field char A")
        self.assertEqual(
            translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_1.tool_name, "Dummy translator")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(
            translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data="Special characters: '\"!? セキレイ",
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, "セキレイ '\"!? characters: Special")
        self.assertEqual(
            translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_3.tool_name, "Dummy translator")
        self.assertEqual(translation_3.last_translated_by, self.user)

    @patch(
        "wagtail_localize.machine_translators.dummy.DummyTranslator.translate",
        side_effect=patched_translate,
    )
    def test_machine_translate_page_with_translate_skip(self, mock_translate_html):
        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        translation_1 = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, "field char A")
        self.assertEqual(
            translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_1.tool_name, "Dummy translator")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(
            translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.filter(
            translation_of__data="Special characters: '\"!? セキレイ",
            context__path="test_richtextfield",
            locale=self.fr_locale,
        ).first()

        self.assertIsNone(translation_3)

    @patch(
        "wagtail_localize.machine_translators.dummy.translate_html",
        side_effect=patched_translate_html,
    )
    def test_machine_translate_page_with_translate_html_skip(self, mock_translate_html):
        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        translation_1 = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, "field char A")
        self.assertEqual(
            translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_1.tool_name, "Dummy translator")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(
            translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.filter(
            translation_of__data="Special characters: '\"!? セキレイ",
            context__path="test_richtextfield",
            locale=self.fr_locale,
        ).first()

        self.assertIsNone(translation_3)

    def test_machine_translate_snippet(self):
        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.snippet_translation.id]
            ),
            {
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        translation = StringTranslation.objects.get(
            translation_of__data="Test snippet",
            context__path="field",
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, "snippet Test")
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation.tool_name, "Dummy translator")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_machine_translate_page_without_next_url(self):
        # You should always call this view with a next URL. But if you forget, it should redirect to the dashboard.

        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            )
        )
        self.assertRedirects(response, reverse("wagtailadmin_home"))

    def test_machine_translate_page_with_existing_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="A char field"),
            context=TranslationContext.objects.get(path="test_charfield"),
            locale=self.fr_locale,
            data="Un champ de caractères",
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        self.assertRedirects(
            response, reverse("wagtailadmin_pages:edit", args=[self.fr_page.id])
        )

        # Existing translations should remain the same
        translation_1 = StringTranslation.objects.get(
            translation_of__data="A char field",
            context__path="test_charfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, "Un champ de caractères")
        self.assertEqual(
            translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation_1.tool_name, "")

        # Additional translations should be added on
        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(
            translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data="Special characters: '\"!? セキレイ",
            context__path="test_richtextfield",
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, "セキレイ '\"!? characters: Special")
        self.assertEqual(
            translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE
        )
        self.assertEqual(translation_3.tool_name, "Dummy translator")
        self.assertEqual(translation_3.last_translated_by, self.user)

    def test_machine_translate_snippet_when_already_translated(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="Test snippet"),
            context=TranslationContext.objects.get(path="field"),
            locale=self.fr_locale,
            data="Extrait de test",
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
        )

        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.snippet_translation.id]
            ),
            {
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                )
            },
        )

        self.assertRedirects(
            response,
            reverse(
                f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                args=[quote(self.fr_snippet.pk)],
            ),
        )

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "warning")

        self.assertEqual(
            messages[0].message,
            "There isn&#x27;t anything left to translate.\n\n\n\n\n",
        )

        translation = StringTranslation.objects.get(
            translation_of__data="Test snippet",
            context__path="field",
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, "Extrait de test")
        self.assertEqual(
            translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL
        )
        self.assertEqual(translation.tool_name, "")

    def test_cant_machine_translate_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()

        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.page_translation.id]
            ),
            {
                "next": reverse("wagtailadmin_pages:edit", args=[self.fr_page.id]),
            },
        )

        assert_permission_denied(self, response)

    def test_cant_machine_translate_without_snippet_perms(self):
        self.moderators_group.permissions.filter(
            content_type=ContentType.objects.get_for_model(TestSnippet)
        ).delete()

        response = self.client.post(
            reverse(
                "wagtail_localize:machine_translate", args=[self.snippet_translation.id]
            ),
            {
                "next": reverse(
                    f"wagtailsnippets_{self.fr_snippet._meta.app_label}_{self.fr_snippet._meta.model_name}:edit",
                    args=[quote(self.fr_snippet.pk)],
                ),
            },
        )

        assert_permission_denied(self, response)


class TestEditAlias(WagtailTestUtils, TestCase):
    """
    Tests that Wagtail Localize's custom edit alias template is rendered for aliases
    that have a different locale to their original.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = cls.create_test_user()
        cls.fr_locale = Locale.objects.create(language_code="fr")

    def setUp(self):
        self.login(username=self.user.username)

        # Create a test page
        self.home_page = Page.objects.get(depth=2)
        self.page = self.home_page.add_child(
            instance=TestPage(
                title="The title",
                slug="test",
            )
        )

        # Set up French locale
        self.fr_home_page = self.home_page.copy_for_translation(self.fr_locale)

    def test_edit_translatable_alias(self):
        # Create an alias of the page in French
        alias_page = self.page.create_alias(
            parent=self.fr_home_page, update_locale=self.fr_locale
        )

        # Try to edit the page
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[alias_page.id])
        )

        # Check the translatable alias template was rendered
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "wagtail_localize/admin/edit_translatable_alias.html"
        )

    def test_edit_non_translatable_alias(self):
        # Create an alias of the page in English
        alias_page = self.page.create_alias(update_slug="test-alias")

        # Try to edit the page
        response = self.client.get(
            reverse("wagtailadmin_pages:edit", args=[alias_page.id])
        )

        # Check the translatable alias template was not rendered
        # Wagtail's builtin edit_alias.html should be rendered instead
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(
            response, "wagtail_localize/admin/edit_translatable_alias.html"
        )
        self.assertTemplateUsed(response, "wagtailadmin/pages/edit_alias.html")
