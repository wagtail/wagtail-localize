from django.test import TestCase

from wagtail_localize.fields import get_translatable_fields, SynchronizedField, TranslatableField

from wagtail_localize.test.models import TestGenerateTranslatableFieldsPage


class TestGetTranslatableFields(TestCase):
    def test(self):
        translatable_fields = get_translatable_fields(TestGenerateTranslatableFieldsPage)

        self.assertEqual(translatable_fields, [
            TranslatableField('title'),
            TranslatableField('slug'),
            TranslatableField('seo_title'),
            SynchronizedField('show_in_menus'),
            TranslatableField('search_description'),
            TranslatableField('test_charfield'),
            SynchronizedField('test_charfield_with_choices'),
            TranslatableField('test_textfield'),
            SynchronizedField('test_emailfield'),
            TranslatableField('test_slugfield'),
            SynchronizedField('test_urlfield'),
            TranslatableField('test_richtextfield'),
            TranslatableField('test_streamfield'),
            TranslatableField('test_snippet'),
            SynchronizedField('test_nontranslatablesnippet'),
            TranslatableField('test_customfield'),
            TranslatableField('test_translatable_childobjects'),
            SynchronizedField('test_nontranslatable_childobjects'),
        ])
