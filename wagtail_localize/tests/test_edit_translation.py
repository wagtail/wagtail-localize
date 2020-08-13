import json
import uuid
import tempfile

import polib
from django import VERSION as DJANGO_VERSION
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APITestCase
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Locale
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import String, StringTranslation, Translation, TranslationContext, TranslationLog, TranslationSource
from wagtail_localize.test.models import TestPage, TestSnippet


RICH_TEXT_DATA = '<h1>This is a heading</h1><p>This is a paragraph. &lt;foo&gt; <b>Bold text</b></p><ul><li><a href="http://example.com">This is a link</a>.</li><li>Special characters: \'"!? セキレイ</li></ul>'

STREAM_BLOCK_ID = uuid.uuid4()
STREAM_DATA = [
    {"id": STREAM_BLOCK_ID, "type": "test_textblock", "value": "This is a text block"}
]


class EditTranslationTestData(WagtailTestUtils):

    def setUp(self):
        self.login()
        self.user = get_user_model().objects.get()

        # Create page
        self.snippet = TestSnippet.objects.create(field="Test snippet")
        self.home_page = Page.objects.get(depth=2)
        self.page = self.home_page.add_child(instance=TestPage(
            title="The title",
            slug="test",
            test_charfield="A char field",
            test_textfield="A text field",
            test_emailfield="email@example.com",
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
            {'isRoot': True, 'title': 'Root', 'exploreUrl': reverse('wagtailadmin_explore_root')},
            {'isRoot': False, 'title': 'Welcome to your new Wagtail site!', 'exploreUrl': reverse('wagtailadmin_explore', args=[self.fr_home_page.id])},
        ])

        self.assertEqual(props['tabs'], ['Content', 'Promote', 'Settings'])

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

        self.assertEqual(props['initialStringTranslations'], [])

        # Check segments
        self.assertEqual(
            [(segment['contentPath'], segment['source']) for segment in props['segments']],
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
                (f'test_streamfield.{STREAM_BLOCK_ID}', 'This is a text block'),
            ]
        )

        # Test locations
        self.assertEqual(props['segments'][0]['location'], {'tab': 'Content', 'field': 'Test charfield', 'blockId': None, 'fieldHelpText': '', 'subField': None})
        self.assertEqual(props['segments'][7]['location'], {'tab': 'Content', 'field': 'Test richtextfield', 'blockId': None, 'fieldHelpText': '', 'subField': None})
        self.assertEqual(props['segments'][9]['location'], {'tab': 'Content', 'field': 'Test textblock', 'blockId': str(STREAM_BLOCK_ID), 'fieldHelpText': '', 'subField': None})
        # TODO: Examples that use fieldHelpText and subField

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
        self.assertEqual(props['tabs'], [''])

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

        self.assertEqual(props['initialStringTranslations'], [])

        # Check segments
        self.assertEqual(
            [(segment['contentPath'], segment['source']) for segment in props['segments']],
            [
                ('field', 'Test snippet'),
            ]
        )

        # Test locations
        self.assertEqual(props['segments'][0]['location'], {'tab': '', 'field': 'Field', 'blockId': None, 'fieldHelpText': '', 'subField': None})


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

        response = self.client.post(reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]), {
            'action': 'publish',
        })

        self.assertRedirects(response, reverse('wagtailadmin_pages:edit', args=[self.fr_page.id]))

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, 'success')

        if DJANGO_VERSION >= (3, 0):
            self.assertEqual(messages[0].message, "Successfully published &#x27;The title&#x27; in French\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, "Successfully published &#39;The title&#39; in French\n\n\n\n\n")

        # Check the page was published
        self.fr_page.refresh_from_db()
        self.assertEqual(self.fr_page.test_charfield, 'Un champ de caractères')
        latest_revision = self.fr_page.get_latest_revision()
        self.assertEqual(latest_revision.user, self.user)

        # Check translation log
        log = TranslationLog.objects.order_by('id').last()
        self.assertEqual(log.source, self.page_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertEqual(log.page_revision, latest_revision)

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
            self.assertEqual(messages[0].message, f"Successfully published &#x27;TestSnippet object ({self.fr_snippet.id})&#x27; in French\n\n\n\n\n")
        else:
            self.assertEqual(messages[0].message, f"Successfully published &#39;TestSnippet object ({self.fr_snippet.id})&#39; in French\n\n\n\n\n")

        # Check the snippet was published
        self.fr_snippet.refresh_from_db()
        self.assertEqual(self.fr_snippet.field, 'Extrait de test')

        # Check translation log
        log = TranslationLog.objects.order_by('id').last()
        self.assertEqual(log.source, self.snippet_source)
        self.assertEqual(log.locale, self.fr_locale)
        self.assertIsNone(log.page_revision)


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
            'comment': 'Translated manually on 21 August 2020',
            'last_translated_by': {
                'avatar_url': '//www.gravatar.com/avatar/0c83f57c786a0b4a39efab23731c7ebc?s=50&d=mm',
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
            'comment': 'Translated manually on 21 August 2020',
            'last_translated_by': {
                'avatar_url': '//www.gravatar.com/avatar/0c83f57c786a0b4a39efab23731c7ebc?s=50&d=mm',
                'full_name': ''
            }
        })

        translation = StringTranslation.objects.get()
        self.assertEqual(translation.translation_of, string)
        self.assertEqual(translation.context, string_segment.context)
        self.assertEqual(translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(translation.tool_name, "")
        self.assertEqual(translation.last_translated_by, self.user)

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
            'comment': 'Machine translated on 21 August 2020',
            'last_translated_by': None,
        })

        self.assertFalse(StringTranslation.objects.exists())

    def test_delete_non_existent_string_translation(self):
        string = String.objects.get(data='A char field')
        string_segment = string.segments.get()

        response = self.client.delete(reverse('wagtail_localize:edit_string_translation', args=[self.page_translation.id, string_segment.id]), follow=True)

        self.assertEqual(response.status_code, 404)


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
        self.assertContains(response, f'msgctxt "test_streamfield.{STREAM_BLOCK_ID}"\nmsgid "This is a text block"\nmsgstr ""')

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
