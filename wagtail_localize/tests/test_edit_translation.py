import json
import uuid
import tempfile
import unittest

import polib
from django import VERSION as DJANGO_VERSION
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as __
from freezegun import freeze_time
from rest_framework.test import APITestCase
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Locale
from wagtail.documents.models import Document
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import SegmentOverride, String, StringTranslation, Translation, TranslationContext, TranslationLog, TranslationSource, OverridableSegment
from wagtail_localize.test.models import TestPage, TestSnippet
from wagtail_localize.wagtail_hooks import SNIPPET_RESTART_TRANSLATION_ENABLED

from .utils import assert_permission_denied


RICH_TEXT_DATA = '<h1>This is a heading</h1><p>This is a paragraph. &lt;foo&gt; <b>Bold text</b></p><ul><li><a href="http://example.com">This is a link</a>.</li><li>Special characters: \'"!? セキレイ</li></ul>'

STREAM_TEXT_BLOCK_ID = uuid.uuid4()
STREAM_STRUCT_BLOCK_ID = uuid.uuid4()

STREAM_DATA = [
    {"id": STREAM_TEXT_BLOCK_ID, "type": "test_textblock", "value": "This is a text block"},
    {"id": STREAM_STRUCT_BLOCK_ID, "type": "test_structblock", "value": {"field_a": "This is a struct", "field_b": "block"}},
]


class EditTranslationTestData(WagtailTestUtils):

    def setUp(self):
        self.login()
        self.user = get_user_model().objects.get()

        # Convert the user into an editor
        self.moderators_group = Group.objects.get(name="Moderators")
        for permission in Permission.objects.filter(content_type=ContentType.objects.get_for_model(TestSnippet)):
            self.moderators_group.permissions.add(permission)
        self.user.is_superuser = False
        self.user.groups.add(self.moderators_group)
        self.user.save()

        # Create page
        self.snippet = TestSnippet.objects.create(field="Test snippet")
        self.home_page = Page.objects.get(depth=2)
        self.page = self.home_page.add_child(instance=TestPage(
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
                TestPage.test_streamfield.field.stream_block, STREAM_DATA, is_lazy=True
            ),
            test_snippet=self.snippet,
        ))

        # Create translations
        self.fr_locale = Locale.objects.create(language_code="fr")

        self.snippet_source, created = TranslationSource.get_or_create_from_instance(self.snippet)
        self.snippet_translation = Translation.objects.create(
            source=self.snippet_source,
            target_locale=self.fr_locale,
        )
        self.snippet_translation.save_target()
        self.fr_snippet = self.snippet.get_translation(self.fr_locale)

        self.page_source, created = TranslationSource.get_or_create_from_instance(self.page)
        self.page_translation = Translation.objects.create(
            source=self.page_source,
            target_locale=self.fr_locale,
        )
        self.page_translation.save_target()
        self.fr_page = self.page.get_translation(self.fr_locale)
        self.fr_home_page = self.home_page.get_translation(self.fr_locale)

        # Create a segment override
        self.overridable_segment = OverridableSegment.objects.get(
            source=self.page_source,
            context__path='test_synchronized_emailfield'
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
        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtail_localize/admin/edit_translation.html')

        # Check props
        props = json.loads(response.context['props'])

        self.assertEqual(props['object']['title'], "The title")
        self.assertTrue(props['object']['isLive'])
        self.assertFalse(props['object']['isLocked'])
        self.assertTrue(props['object']['lastPublishedDate'])
        self.assertEqual(props['object']['liveUrl'], 'http://localhost/fr/test/')

        self.assertEqual(props['breadcrumb'], [
            {'id': 1, 'isRoot': True, 'title': 'Root', 'exploreUrl': reverse('wagtailadmin_explore_root')},
            {'id': self.fr_home_page.id, 'isRoot': False, 'title': 'Welcome to your new Wagtail site!', 'exploreUrl': reverse('wagtailadmin_explore', args=[self.fr_home_page.id])},
        ])

        self.assertEqual(props['tabs'], [
            {'label': 'Content', 'slug': 'content'},
            {'label': 'Promote', 'slug': 'promote'},
            {'label': 'Settings', 'slug': 'settings'}
        ])

        self.assertEqual(props['sourceLocale'], {'code': 'en', 'displayName': 'English'})
        self.assertEqual(props['locale'], {'code': 'fr', 'displayName': 'French'})

        self.assertEqual(props['translations'], [
            {'title': 'The title', 'locale': {'code': 'en', 'displayName': 'English'}, 'editUrl': reverse('wagtailadmin_pages:edit', args=[self.page.id])}
        ])

        self.assertTrue(props['perms']['canPublish'])
        self.assertTrue(props['perms']['canUnpublish'])
        self.assertTrue(props['perms']['canLock'])
        self.assertTrue(props['perms']['canUnlock'])
        self.assertTrue(props['perms']['canDelete'])

        self.assertEqual(props['links']['unpublishUrl'], reverse('wagtailadmin_pages:unpublish', args=[self.fr_page.id]))
        self.assertEqual(props['links']['lockUrl'], reverse('wagtailadmin_pages:lock', args=[self.fr_page.id]))
        self.assertEqual(props['links']['unlockUrl'], reverse('wagtailadmin_pages:unlock', args=[self.fr_page.id]))
        self.assertEqual(props['links']['deleteUrl'], reverse('wagtailadmin_pages:delete', args=[self.fr_page.id]))

        self.assertEqual(props['previewModes'], [
            {'mode': '', 'label': 'Default', 'url': reverse('wagtail_localize:preview_translation', args=[self.page_translation.id])}
        ])

        self.assertEqual(props['initialStringTranslations'], [])
        self.assertEqual(props['initialOverrides'], [{'data': 'overridden@example.com', 'error': None, 'segment_id': self.overridable_segment.id}])

        # Check segments
        self.assertEqual(
            [(segment['contentPath'], segment['source']) for segment in props['segments'] if segment['type'] == 'string'],
            [
                ('test_charfield', 'A char field'),
                ('test_textfield', 'A text field'),
                ('test_emailfield', 'email@example.com'),
                ('test_slugfield', 'a-slug-field'),
                ('test_urlfield', 'https://www.example.com'),
                ('test_richtextfield', 'This is a heading'),
                ('test_richtextfield', 'This is a paragraph. &lt;foo&gt; <b>Bold text</b>'),
                ('test_richtextfield', '<a id="a1">This is a link</a>.'),
                ('test_richtextfield', 'Special characters: \'"!? セキレイ'),
                (f'test_streamfield.{STREAM_TEXT_BLOCK_ID}', 'This is a text block'),
                (f'test_streamfield.{STREAM_STRUCT_BLOCK_ID}.field_a', 'This is a struct'),
                (f'test_streamfield.{STREAM_STRUCT_BLOCK_ID}.field_b', 'block'),
            ]
        )
        self.assertEqual(
            [(segment['contentPath'], segment['value']) for segment in props['segments'] if segment['type'] == 'synchronised_value'],
            [
                ('test_synchronized_emailfield', 'email@example.com'),
            ]
        )

        # Test locations
        self.assertEqual(props['segments'][0]['location'], {'tab': 'content', 'field': 'Char field', 'blockId': None, 'fieldHelpText': '', 'subField': None, 'widget': None})
        self.assertEqual(props['segments'][7]['location'], {'tab': 'content', 'field': 'Test richtextfield', 'blockId': None, 'fieldHelpText': '', 'subField': None, 'widget': None})
        self.assertEqual(props['segments'][9]['location'], {'tab': 'content', 'field': 'Text block', 'blockId': str(STREAM_TEXT_BLOCK_ID), 'fieldHelpText': '', 'subField': None, 'widget': None})
        self.assertEqual(props['segments'][10]['location'], {'tab': 'content', 'field': 'Test structblock', 'blockId': str(STREAM_STRUCT_BLOCK_ID), 'fieldHelpText': '', 'subField': 'Field a', 'widget': None})
        # TODO: Example that uses fieldHelpText

        # Check related object
        related_object_segment = props['segments'][12]
        self.assertEqual(related_object_segment['type'], 'related_object')
        self.assertEqual(related_object_segment['contentPath'], 'test_snippet')
        self.assertEqual(related_object_segment['location'], {'tab': 'content', 'field': 'Test snippet', 'blockId': None, 'fieldHelpText': '', 'subField': None, 'widget': None})
        self.assertEqual(related_object_segment['source']['title'], str(self.snippet))
        self.assertEqual(related_object_segment['dest']['title'], str(self.fr_snippet))
        self.assertEqual(related_object_segment['translationProgress'], {'totalSegments': 1, 'translatedSegments': 0})

    def test_manually_translated_related_object(self):
        # Related objects don't have to be translated by Wagtail localize so test with the snippet's translation record deleted
        self.snippet_translation.delete()

        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtail_localize/admin/edit_translation.html')

        props = json.loads(response.context['props'])

        # Check related object
        related_object_segment = props['segments'][12]
        self.assertEqual(related_object_segment['type'], 'related_object')
        self.assertEqual(related_object_segment['contentPath'], 'test_snippet')
        self.assertEqual(related_object_segment['location'], {'tab': 'content', 'field': 'Test snippet', 'blockId': None, 'fieldHelpText': '', 'subField': None, 'widget': None})
        self.assertEqual(related_object_segment['source']['title'], str(self.snippet))
        self.assertEqual(related_object_segment['dest']['title'], str(self.fr_snippet))
        self.assertIsNone(related_object_segment['translationProgress'])

    def test_override_types(self):
        # Similar to above but adds some more overridable things to test with
        self.page.test_synchronized_image = Image.objects.create(
            title="Test image",
            file=get_test_image_file()
        )
        self.page.test_synchronized_document = Document.objects.create(
            title="Test document",
            file=get_test_image_file()
        )
        self.page.test_synchronized_snippet = self.snippet

        url_block_id = uuid.uuid4()
        page_block_id = uuid.uuid4()
        image_block_id = uuid.uuid4()
        document_block_id = uuid.uuid4()
        snippet_block_id = uuid.uuid4()
        stream_data = [
            {"id": str(url_block_id), "type": "test_urlblock", "value": "https://wagtail.io/"},
            {"id": str(page_block_id), "type": "test_pagechooserblock", "value": self.page.id},
            {"id": str(image_block_id), "type": "test_imagechooserblock", "value": self.page.test_synchronized_image.id},
            {"id": str(document_block_id), "type": "test_documentchooserblock", "value": self.page.test_synchronized_document.id},
            {"id": str(snippet_block_id), "type": "test_snippetchooserblock", "value": self.snippet.id},
        ]

        self.page.test_streamfield = TestPage.test_streamfield.field.to_python(json.dumps(stream_data))

        self.page.save_revision().publish()
        TranslationSource.update_or_create_from_instance(self.page)

        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))
        self.assertEqual(response.status_code, 200)

        # Check props
        props = json.loads(response.context['props'])

        self.assertEqual(
            [(segment['contentPath'], segment['location']['widget'], segment['value']) for segment in props['segments'] if segment['type'] == 'synchronised_value'],
            [
                (f'test_streamfield.{url_block_id}', {'type': 'text'}, "https://wagtail.io/"),
                (f'test_streamfield.{image_block_id}', {'type': 'image_chooser'}, self.page.test_synchronized_image.id),
                (f'test_streamfield.{document_block_id}', {'type': 'document_chooser'}, self.page.test_synchronized_document.id),
                ('test_synchronized_emailfield', {'type': 'text'}, 'email@example.com'),
                ('test_synchronized_image', {'type': 'image_chooser'}, self.page.test_synchronized_image.id),
                ('test_synchronized_document', {'type': 'document_chooser'}, self.page.test_synchronized_document.id),
                ('test_synchronized_snippet', {'type': 'unknown'}, self.snippet.id),
            ]
        )

    def test_edit_page_translation_with_multi_mode_preview(self):
        # Add some extra preview modes to the page
        previous_preview_modes = TestPage.preview_modes
        TestPage.preview_modes = [
            ('', __("Default")),
            ('first-mode', __("First mode")),
            ('second-mode', __("Second mode")),
        ]

        try:
            response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))
        finally:
            TestPage.preview_modes = previous_preview_modes

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtail_localize/admin/edit_translation.html')

        # Check props
        props = json.loads(response.context['props'])

        self.assertEqual(props['previewModes'], [
            {'mode': '', 'label': 'Default', 'url': reverse('wagtail_localize:preview_translation', args=[self.page_translation.id])},
            {'mode': 'first-mode', 'label': 'First mode', 'url': reverse('wagtail_localize:preview_translation', args=[self.page_translation.id, 'first-mode'])},
            {'mode': 'second-mode', 'label': 'Second mode', 'url': reverse('wagtail_localize:preview_translation', args=[self.page_translation.id, 'second-mode'])},
        ])

    def test_cant_edit_page_translation_without_perms(self):
        self.moderators_group.page_permissions.all().delete()
        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))
        assert_permission_denied(self, response)

    def test_edit_snippet_translation(self):
        response = self.client.get(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtail_localize/admin/edit_translation.html')

        # Check props
        props = json.loads(response.context['props'])

        self.assertEqual(props['object']['title'], f"TestSnippet object ({self.fr_snippet.id})")
        self.assertTrue(props['object']['isLive'])
        self.assertFalse(props['object']['isLocked'])

        # Snippets don't have last published, live URL, breadcrumb, or tabs
        self.assertIsNone(props['object']['lastPublishedDate'])
        self.assertIsNone(props['object']['liveUrl'])
        self.assertEqual(props['breadcrumb'], [])
        self.assertEqual(props['tabs'], [{'label': 'Content', 'slug': 'content'}])

        self.assertEqual(props['sourceLocale'], {'code': 'en', 'displayName': 'English'})
        self.assertEqual(props['locale'], {'code': 'fr', 'displayName': 'French'})

        self.assertEqual(props['translations'], [
            {'title': f"TestSnippet object ({self.snippet.id})", 'locale': {'code': 'en', 'displayName': 'English'}, 'editUrl': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.snippet.id])}
        ])

        self.assertTrue(props['perms']['canPublish'])
        self.assertFalse(props['perms']['canUnpublish'])
        self.assertFalse(props['perms']['canLock'])
        self.assertFalse(props['perms']['canUnlock'])
        self.assertTrue(props['perms']['canDelete'])

        self.assertIsNone(props['links']['unpublishUrl'])
        self.assertIsNone(props['links']['lockUrl'])
        self.assertIsNone(props['links']['unlockUrl'])
        self.assertEqual(props['links']['deleteUrl'], reverse('wagtailsnippets:delete', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        self.assertEqual(props['previewModes'], [])

        self.assertEqual(props['initialStringTranslations'], [])

        # Check segments
        self.assertEqual(
            [(segment['contentPath'], segment['source']) for segment in props['segments']],
            [
                ('field', 'Test snippet'),
            ]
        )

        # Test locations
        self.assertEqual(props['segments'][0]['location'], {'tab': '', 'field': 'Field', 'blockId': None, 'fieldHelpText': '', 'subField': None, 'widget': None})

    def test_cant_edit_snippet_translation_without_perms(self):
        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()
        response = self.client.get(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        assert_permission_denied(self, response)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].message, "Sorry, you do not have permission to access this area.\n\n\n\n\n")


@freeze_time('2020-08-21')
class TestPublishTranslation(EditTranslationTestData, APITestCase):
    def test_publish_page_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Un champ de caractères',
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        # Fill all the remaining fields so that we don't get a warning message
        string_segments = self.page_translation.source.stringsegment_set.all().order_by('order')
        for segment in string_segments.annotate_translation(self.fr_locale).filter(translation__isnull=True):
            StringTranslation.objects.create(
                translation_of=segment.string,
                context=segment.context,
                locale=self.fr_locale,
                data=segment.string.data,
                translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
            )

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "Published &#x27;The title&#x27; in French.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "Published &#39;The title&#39; in French.\n\n\n\n\n")

        # Check the page was published
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, 'Un champ de caractères')
        latest_revision = self.fr_page.get_latest_revision()
        self.assertEqual(latest_revision.user, self.user)

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.page_revision, latest_revision)

    def test_publish_page_translation_with_missing_translations(self):
        # Same as the above test except we only fill in one field. We should be given a warning but the publish should be published.
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Un champ de caractères',
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'warning')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "Published &#x27;The title&#x27; in French with missing translations - see below.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "Published &#39;The title&#39; in French with missing translations - see below.\n\n\n\n\n")

        # Check the page was published
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, 'Un champ de caractères')
        latest_revision = self.fr_page.get_latest_revision()
        self.assertEqual(latest_revision.user, self.user)

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.page_revision, latest_revision)

    def test_publish_page_translation_with_new_field_error(self):
        translation = StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data=(
                'This value is way too long for a char field so it should fail to publish and add an error to the translation. '
                'This value is way too long for a char field so it should fail to publish and add an error to the translation. '
                'This value is way too long for a char field so it should fail to publish and add an error to the translation.'
            ),
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "New validation errors were found when publishing &#x27;The title&#x27; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "New validation errors were found when publishing &#39;The title&#39; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n")

        # Check that the test_charfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, 'A char field')

        # Check specific error was added to the translation
        translation.refresh_from_db()
        self.assertTrue(translation.has_error)
        self.assertEqual(translation.get_error(), "Ensure this value has at most 255 characters (it has 329).")

        # Check page was not published
        self.assertFalse(TranslationLog.objects.exists())

    def test_publish_page_translation_with_known_field_error(self):
        # Same as previous test, except the error is already known at the point of publishing the page. So the page is published
        # but the invalid field is ignored.
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data=(
                'This value is way too long for a char field so it should fail to publish and add an error to the translation. '
                'This value is way too long for a char field so it should fail to publish and add an error to the translation. '
                'This value is way too long for a char field so it should fail to publish and add an error to the translation.'
            ),
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL,
            has_error=True,
            field_error="Ensure this value has at most 255 characters (it has 329).",
        )

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'warning')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "Published &#x27;The title&#x27; in French with missing translations - see below.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "Published &#39;The title&#39; in French with missing translations - see below.\n\n\n\n\n")

        # Check that the test_charfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, 'A char field')

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.page_revision, self.fr_page.get_latest_revision())

    def test_publish_page_translation_with_invalid_segment_override(self):
        # Set the email address override to something invalid
        self.segment_override.data_json = '"Definitely not an email address"'
        self.segment_override.save()

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "New validation errors were found when publishing &#x27;The title&#x27; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "New validation errors were found when publishing &#39;The title&#39; in French. Please fix them or click publish again to ignore these translations for now.\n\n\n\n\n")

        # Check that the test_synchronized_emailfield was not changed
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_synchronized_emailfield, 'email@example.com')

        # Check specific error was added to the override
        self.segment_override.refresh_from_db()
        self.assertTrue(self.segment_override.has_error)
        self.assertEqual(self.segment_override.get_error(), "Enter a valid email address.")

        # Check page was not published
        self.assertFalse(TranslationLog.objects.exists())

    def test_cant_publish_page_translation_without_perms(self):
        self.moderators_group.page_permissions.filter(permission_type='publish').delete()
        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })
        assert_permission_denied(self, response)

    def test_publish_snippet_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data="Test snippet"),
            context=TranslationContext.objects.get(path="field"),
            locale=self.fr_locale,
            data="Extrait de test"
        )

        response = self.client.post(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, f"Published &#x27;TestSnippet object ({self.fr_snippet.id})&#x27; in French.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, f"Published &#39;TestSnippet object ({self.fr_snippet.id})&#39; in French.\n\n\n\n\n")

        # Check the snippet was published
        self.fr_snippet.refresh_from_db()
        self.assertEqual(self.fr_snippet.field, 'Extrait de test')

        # Check translation log
        log = TranslationLog.objects.get()
        self.assertEqual(log.source, self.snippet_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertIsNone(log.page_revision)

    def test_cant_publish_snippet_translation_without_perms(self):
        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()

        response = self.client.post(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]), {
            'action': 'publish',
        })

        assert_permission_denied(self, response)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].message, "Sorry, you do not have permission to access this area.\n\n\n\n\n")


class TestPreviewTranslationView(EditTranslationTestData, TestCase):
    def test_preview_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Un champ de caractères',
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        response = self.client.get(reverse('wagtail_localize:preview_translation', args=[self.page_translation.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TestPage.template)
        self.assertContains(response, 'Un champ de caractères')


class TestStopTranslationView(EditTranslationTestData, TestCase):
    def test_stop_translation(self):
        response = self.client.post(reverse('wagtail_localize:stop_translation', args=[self.page_translation.id]), {
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        self.page_translation.refresh_from_db()
        self.assertFalse(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].message, "Translation has been stopped.\n\n\n\n\n")

    def test_stop_translation_without_next_url(self):
        # You should always call this view with a next URL. But if you forget, it should redirect to the dashboard.

        response = self.client.post(reverse('wagtail_localize:stop_translation', args=[self.page_translation.id]))

        self.assertRedirects(response, reverse('wagtailadmin_home'))

        self.page_translation.refresh_from_db()
        self.assertFalse(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].message, "Translation has been stopped.\n\n\n\n\n")


class TestRestartTranslation(EditTranslationTestData, TestCase):
    def test_restart_page_translation(self):
        self.page_translation.enabled = False
        self.page_translation.save()
        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'localize-restart-translation': 'yes',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        self.page_translation.refresh_from_db()
        self.assertTrue(self.page_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].message, "Translation has been restarted.\n\n\n\n\n")

    def test_restart_snippet_translation(self):
        self.snippet_translation.enabled = False
        self.snippet_translation.save()
        response = self.client.post(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]), {
            'localize-restart-translation': 'yes',
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        self.snippet_translation.refresh_from_db()
        self.assertTrue(self.snippet_translation.enabled)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].message, "Translation has been restarted.\n\n\n\n\n")


class TestRestartTranslationButton(EditTranslationTestData, TestCase):
    def test_page(self):
        self.page_translation.enabled = False
        self.page_translation.save()

        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        self.assertContains(response, "Restart translation")

    def test_doesnt_show_when_no_translation_for_page(self):
        self.page_translation.delete()

        response = self.client.get(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        self.assertNotContains(response, "Restart translation")

    @unittest.skipUnless(SNIPPET_RESTART_TRANSLATION_ENABLED, "wagtail.snippets.action_menu module doesn't exist. See: https://github.com/wagtail/wagtail/pull/6384")
    def test_snippet(self):
        self.snippet_translation.enabled = False
        self.snippet_translation.save()

        response = self.client.get(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        self.assertContains(response, "Restart translation")

    @unittest.skipUnless(SNIPPET_RESTART_TRANSLATION_ENABLED, "wagtail.snippets.action_menu module doesn't exist. See: https://github.com/wagtail/wagtail/pull/6384")
    def test_doesnt_show_when_no_translation_for_snippet(self):
        self.snippet_translation.delete()

        response = self.client.get(reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        self.assertNotContains(response, "Restart translation")

    @unittest.skipUnless(SNIPPET_RESTART_TRANSLATION_ENABLED, "wagtail.snippets.action_menu module doesn't exist. See: https://github.com/wagtail/wagtail/pull/6384")
    def test_doesnt_show_on_create_for_snippet(self):
        response = self.client.get(reverse('wagtailsnippets:add', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name]))
        self.assertNotContains(response, "Restart translation")


@freeze_time('2020-08-21')
class TestEditStringTranslationAPIView(EditTranslationTestData, APITestCase):
    def test_create_string_translation(self):
        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.put(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), {
            'value': 'Un champ de caractères',
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'string_id': string.id,
            'segment_id': string_segment.id,
            'data': 'Un champ de caractères',
            'error': None,
            'comment': 'Translated manually on 21 August 2020',
            'last_translated_by': {
                'avatar_url': '//www.gravatar.com/avatar/93942e96f5acd83e2e047ad8fe03114d?s=50&d=mm',
                'full_name': ''
            }
        })

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_update_string_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Not translated!',
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE
        )

        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.put(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), {
            'value': 'Un champ de caractères',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'string_id': string.id,
            'segment_id': string_segment.id,
            'data': 'Un champ de caractères',
            'error': None,
            'comment': 'Translated manually on 21 August 2020',
            'last_translated_by': {
                'avatar_url': '//www.gravatar.com/avatar/93942e96f5acd83e2e047ad8fe03114d?s=50&d=mm',
                'full_name': ''
            }
        })

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_update_string_translation_with_bad_html(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Not translated!',
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE
        )

        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.put(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), {
            'value': 'Un champ de caractères <script>Some nasty JS</script>',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'string_id': string.id,
            'segment_id': string_segment.id,
            'data': 'Un champ de caractères <script>Some nasty JS</script>',
            'error': '<script> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)',
            'comment': 'Translated manually on 21 August 2020',
            'last_translated_by': {
                'avatar_url': '//www.gravatar.com/avatar/93942e96f5acd83e2e047ad8fe03114d?s=50&d=mm',
                'full_name': ''
            }
        })

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)
        self.assertTrue(translation.has_error)

    def test_delete_string_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Not translated!',
            translation_type=StringTranslation.TRANSLATION_TYPE_MACHINE
        )

        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.delete(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]))

        # Response should contain the deleted string
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'string_id': string.id,
            'segment_id': string_segment.id,
            'data': 'Not translated!',
            'error': None,
            'comment': 'Machine translated on 21 August 2020',
            'last_translated_by': None,
        })

        self.assertFalse(StringTranslation.objects.exists())

    def test_delete_non_existent_string_translation(self):
        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.delete(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), follow=True)

        self.assertEqual(response.status_code, 404)

    def test_cant_edit_translation_without_page_perms(self):
        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        self.moderators_group.page_permissions.all().delete()

        response = self.client.put(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), {
            'value': 'Un champ de caractères',
        })

        self.assertEquals(response.status_code, 403)

    def test_cant_edit_translation_without_snippet_perms(self):
        string = String.objects.get(data='Test snippet')
        string_segment = string.segments.get()

        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()

        response = self.client.put(reverse('wagtail_localize:edit_string_translation', args=[self.snippet_translation.id, string_segment.id]), {
            'value': 'Un champ de caractères',
        })

        self.assertEquals(response.status_code, 403)


@freeze_time('2020-08-21')
class TestEditOverrideAPIView(EditTranslationTestData, APITestCase):
    def test_create_override(self):
        self.segment_override.delete()

        response = self.client.put(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]), {
            'value': 'overridden_by_view@example.com',
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'segment_id': self.overridable_segment.id,
            'error': None,
            'data': 'overridden_by_view@example.com',
        })

        override = SegmentOverride.objects.get()
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"overridden_by_view@example.com"')

    def test_update_override(self):
        response = self.client.put(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]), {
            'value': 'updated_by_view@example.com',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'segment_id': self.overridable_segment.id,
            'error': None,
            'data': 'updated_by_view@example.com',
        })

        override = SegmentOverride.objects.get()
        self.assertEqual(override.id, self.segment_override.id)
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"updated_by_view@example.com"')

    def test_update_override_with_invalid_value(self):
        # Overrides are not currently validated on save.
        # But they are validated when the page/snippet is published.
        # TODO (someday): Would be nice to have the validation here
        response = self.client.put(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]), {
            'value': 'Definitely not an email address',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'segment_id': self.overridable_segment.id,
            'error': None,
            'data': 'Definitely not an email address',
        })

        override = SegmentOverride.objects.get()
        self.assertEqual(override.id, self.segment_override.id)
        self.assertEqual(override.context, self.overridable_segment.context)
        self.assertEqual(override.locale, self.fr_locale)
        self.assertEqual(override.data_json, '"Definitely not an email address"')

    def test_delete_override(self):
        response = self.client.delete(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {
            'segment_id': self.overridable_segment.id,
            'error': None,
            'data': 'overridden@example.com',
        })

        self.assertFalse(SegmentOverride.objects.exists())

    def test_delete_non_existent_override(self):
        self.segment_override.delete()

        response = self.client.delete(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]), follow=True)

        self.assertEqual(response.status_code, 404)

    def test_cant_edit_overrides_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()

        response = self.client.put(reverse('wagtail_localize:edit_override', args=[self.page_translation.id, self.overridable_segment.id]), {
            'value': 'updated_by_view@example.com',
        })

        self.assertEquals(response.status_code, 403)


class TestDownloadPOFileView(EditTranslationTestData, TestCase):
    def test_download_pofile_page(self):
        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.page_translation.id]))

        self.assertContains(response, f'X-WagtailLocalize-TranslationID: {str(self.page_translation.uuid)}')
        self.assertContains(response, 'msgctxt "test_charfield"\nmsgid "A char field"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_textfield"\nmsgid "A text field"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_emailfield"\nmsgid "email@example.com"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_slugfield"\nmsgid "a-slug-field"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_urlfield"\nmsgid "https://www.example.com"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_richtextfield"\nmsgid "This is a heading"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_richtextfield"\nmsgid "This is a paragraph. &lt;foo&gt; <b>Bold text</b>"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_richtextfield"\nmsgid "<a id=\\"a1\\">This is a link</a>."\nmsgstr ""')
        self.assertContains(response, 'msgctxt "test_richtextfield"\nmsgid "Special characters: \'\\"!? セキレイ"\nmsgstr ""')
        self.assertContains(response, f'msgctxt "test_streamfield.{STREAM_TEXT_BLOCK_ID}"\nmsgid "This is a text block"\nmsgstr ""')

    def test_download_pofile_snippet(self):
        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.snippet_translation.id]))

        self.assertContains(response, f'X-WagtailLocalize-TranslationID: {str(self.snippet_translation.uuid)}')
        self.assertContains(response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr ""')

    def test_includes_existing_translations(self):
        string = String.objects.get(data="Test snippet")
        context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=string,
            context=context,
            locale=self.fr_locale,
            data="Extrait de test"
        )

        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.snippet_translation.id]))
        self.assertContains(response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr "Extrait de test"')

    def test_includes_obsolete_translations(self):
        string = String.objects.create(locale=Locale.objects.get(language_code="en"), data="A string that is no longer used on the snippet")
        context = TranslationContext.objects.get(path="field")
        StringTranslation.objects.create(
            translation_of=string,
            context=context,
            locale=self.fr_locale,
            data="Une chaîne qui n'est plus utilisée sur l'extrait"
        )

        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.snippet_translation.id]))

        self.assertContains(response, 'msgctxt "field"\nmsgid "Test snippet"\nmsgstr ""')
        self.assertContains(response, 'msgctxt "field"\n#~ msgid "A string that is no longer used on the snippet"\n#~ msgstr "Une chaîne qui n\'est plus utilisée sur l\'extrait"')

    def test_cant_download_pofile_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()
        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.page_translation.id]))
        assert_permission_denied(self, response)

    def test_cant_download_pofile_without_snippet_perms(self):
        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()
        response = self.client.get(reverse('wagtail_localize:download_pofile', args=[self.snippet_translation.id]))
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
                msgid='A char field',
                msgctxt='test_charfield',
                msgstr='Un champ de caractères',
            )
        )

        po.append(
            polib.POEntry(
                msgid='<a id="a1">This is a link</a>.',
                msgctxt='test_richtextfield',
                msgstr='<a id="a1">Ceci est un lien</a>.',
            )
        )

        po.append(
            polib.POEntry(
                msgid='Special characters: \'"!? セキレイ',
                msgctxt='test_richtextfield',
                msgstr='Caractères spéciaux: \'"!? セキレイ',
            )
        )

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.page_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        translation_1 = StringTranslation.objects.get(
            translation_of__data='A char field',
            context__path='test_charfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, 'Un champ de caractères')
        self.assertEqual(translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation_1.tool_name, "PO File")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '<a id="a1">Ceci est un lien</a>.')
        self.assertEqual(translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation_2.tool_name, "PO File")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data='Special characters: \'"!? セキレイ',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, 'Caractères spéciaux: \'"!? セキレイ')
        self.assertEqual(translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
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
                msgid='Test snippet',
                msgctxt='field',
                msgstr='Extrait de test',
            )
        )

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.snippet_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        translation = StringTranslation.objects.get(
            translation_of__data='Test snippet',
            context__path='field',
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, 'Extrait de test')
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "PO File")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_upload_pofile_page_without_strings(self):
        # You can leave strings out, this shouldn't affect existing translations

        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Un champ de caractères'
        )

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.page_translation.uuid),
        }

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.page_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Existing translation should be uneffected
        translation = StringTranslation.objects.get(
            translation_of__data='A char field',
            context__path='test_charfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, 'Un champ de caractères')
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

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.page_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
        })

        self.assertRedirects(response, reverse('wagtailadmin_home'))

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
                msgid='A tweaked char field',
                msgctxt='test_charfield',
                msgstr='Un champ de caractères',
            )
        )

        # Context not recognised
        po.append(
            polib.POEntry(
                msgid='A char field',
                msgctxt='test_charfield_badcontext',
                msgstr='Un champ de caractères',
            )
        )

        # Uploaded against wrong object
        po.append(
            polib.POEntry(
                msgid='Test snippet',
                msgctxt='field',
                msgstr='Extrait de test',
            )
        )

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.page_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Neither string should be imported
        self.assertFalse(StringTranslation.objects.exists())

    def test_upload_pofile_snippet_invalid_file(self):
        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.snippet_translation.id]), {
            'file': SimpleUploadedFile("translations.po", "Foo".encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].message, "Please upload a valid PO file.\n\n\n\n\n")

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
                msgid='Test snippet',
                msgctxt='field',
                msgstr='Extrait de test',
            )
        )

        with tempfile.NamedTemporaryFile() as f:
            f.write(str(po).encode('utf-8'))
            f.flush()

            response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.snippet_translation.id]), {
                'file': SimpleUploadedFile("translations.po", f.name.encode('utf-8'), content_type="text/x-gettext-translation"),
                'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
            })

            self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

            # User should be warned with a message
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(messages[0].level_tag, 'error')
            self.assertEqual(messages[0].message, "Please upload a valid PO file.\n\n\n\n\n")

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
                msgid='Test snippet',
                msgctxt='field',
                msgstr='Extrait de test',
            )
        )

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.snippet_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].message, "Cannot import PO file that was created for a different translation.\n\n\n\n\n")

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

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.page_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        assert_permission_denied(self, response)

    def test_cant_upload_pofile_without_snippet_perms(self):
        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()

        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.snippet_translation.uuid),
        }

        response = self.client.post(reverse('wagtail_localize:upload_pofile', args=[self.snippet_translation.id]), {
            'file': SimpleUploadedFile("translations.po", str(po).encode('utf-8'), content_type="text/x-gettext-translation"),
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        assert_permission_denied(self, response)


class TestMachineTranslateView(EditTranslationTestData, TestCase):
    def test_machine_translate_page(self):
        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.page_translation.id]), {
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        translation_1 = StringTranslation.objects.get(
            translation_of__data='A char field',
            context__path='test_charfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, 'field char A')
        self.assertEqual(translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation_1.tool_name, "Dummy translator")
        self.assertEqual(translation_1.last_translated_by, self.user)

        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data='Special characters: \'"!? セキレイ',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, 'セキレイ \'"!? characters: Special')
        self.assertEqual(translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation_3.tool_name, "Dummy translator")
        self.assertEqual(translation_3.last_translated_by, self.user)

    def test_machine_translate_snippet(self):
        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.snippet_translation.id]), {
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        translation = StringTranslation.objects.get(
            translation_of__data='Test snippet',
            context__path='field',
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, 'snippet Test')
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation.tool_name, "Dummy translator")
        self.assertEqual(translation.last_translated_by, self.user)

    def test_machine_translate_page_without_next_url(self):
        # You should always call this view with a next URL. But if you forget, it should redirect to the dashboard.

        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.page_translation.id]))
        self.assertRedirects(response, reverse('wagtailadmin_home'))

    def test_machine_translate_page_with_existing_translation(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='A char field'),
            context=TranslationContext.objects.get(path='test_charfield'),
            locale=self.fr_locale,
            data='Un champ de caractères',
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.page_translation.id]), {
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Existing translations should remain the same
        translation_1 = StringTranslation.objects.get(
            translation_of__data='A char field',
            context__path='test_charfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_1.data, 'Un champ de caractères')
        self.assertEqual(translation_1.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation_1.tool_name, "")

        # Additional translations should be added on
        translation_2 = StringTranslation.objects.get(
            translation_of__data='<a id="a1">This is a link</a>.',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_2.data, '.<a id="a1">link a is This</a>')
        self.assertEqual(translation_2.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation_2.tool_name, "Dummy translator")
        self.assertEqual(translation_2.last_translated_by, self.user)

        translation_3 = StringTranslation.objects.get(
            translation_of__data='Special characters: \'"!? セキレイ',
            context__path='test_richtextfield',
            locale=self.fr_locale,
        )

        self.assertEqual(translation_3.data, 'セキレイ \'"!? characters: Special')
        self.assertEqual(translation_3.translation_type, StringTranslation.TRANSLATION_TYPE_MACHINE)
        self.assertEqual(translation_3.tool_name, "Dummy translator")
        self.assertEqual(translation_3.last_translated_by, self.user)

    def test_machine_translate_snippet_when_already_translated(self):
        StringTranslation.objects.create(
            translation_of=String.objects.get(data='Test snippet'),
            context=TranslationContext.objects.get(path='field'),
            locale=self.fr_locale,
            data='Extrait de test',
            translation_type=StringTranslation.TRANSLATION_TYPE_MANUAL
        )

        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.snippet_translation.id]), {
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        self.assertRedirects(response, reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]))

        # User should be warned with a message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'warning')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "There isn&#x27;t anything left to translate.\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "There isn&#39;t anything left to translate.\n\n\n\n\n")

        translation = StringTranslation.objects.get(
            translation_of__data='Test snippet',
            context__path='field',
            locale=self.fr_locale,
        )

        self.assertEqual(translation.data, 'Extrait de test')
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "")

    def test_cant_machine_translate_without_page_perms(self):
        self.moderators_group.page_permissions.all().delete()

        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.page_translation.id]), {
            'next': reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]),
        })

        assert_permission_denied(self, response)

    def test_cant_machine_translate_without_snippet_perms(self):
        self.moderators_group.permissions.filter(content_type=ContentType.objects.get_for_model(TestSnippet)).delete()

        response = self.client.post(reverse('wagtail_localize:machine_translate', args=[self.snippet_translation.id]), {
            'next': reverse('wagtailsnippets:edit', args=[TestSnippet._meta.app_label, TestSnippet._meta.model_name, self.fr_snippet.id]),
        })

        assert_permission_denied(self, response)
