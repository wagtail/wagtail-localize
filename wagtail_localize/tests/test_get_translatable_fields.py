from django.test import TestCase
from wagtail.models import Locale

from wagtail_localize.fields import (
    SynchronizedField,
    TranslatableField,
    copy_synchronised_fields,
    get_translatable_fields,
)
from wagtail_localize.test.models import (
    NonTranslatableSnippet,
    TestGenerateTranslatableFieldsPage,
    TestM2MSnippet,
    TestOverrideTranslatableFieldsPage,
)


class TestGetTranslatableFields(TestCase):
    def test(self):
        translatable_fields = get_translatable_fields(
            TestGenerateTranslatableFieldsPage
        )

        self.assertEqual(
            translatable_fields,
            [
                TranslatableField("title"),
                TranslatableField("slug"),
                TranslatableField("seo_title"),
                SynchronizedField("show_in_menus"),
                TranslatableField("search_description"),
                TranslatableField("test_charfield"),
                SynchronizedField("test_charfield_with_choices"),
                TranslatableField("test_textfield"),
                SynchronizedField("test_emailfield"),
                TranslatableField("test_slugfield"),
                SynchronizedField("test_urlfield"),
                TranslatableField("test_richtextfield"),
                TranslatableField("test_streamfield"),
                TranslatableField("test_snippet"),
                SynchronizedField("test_nontranslatablesnippet"),
                TranslatableField("test_customfield"),
                TranslatableField("test_translatable_childobjects"),
                SynchronizedField("test_nontranslatable_childobjects"),
            ],
        )


class TestOverrideTranslatableFields(TestCase):
    def test(self):
        translatable_fields = get_translatable_fields(
            TestOverrideTranslatableFieldsPage
        )

        self.assertEqual(
            translatable_fields,
            [
                TranslatableField("title"),
                TranslatableField("slug"),
                TranslatableField("seo_title"),
                SynchronizedField("show_in_menus"),
                TranslatableField("search_description"),
                SynchronizedField("test_charfield"),  # Overriden!
                SynchronizedField("test_charfield_with_choices"),
                TranslatableField("test_textfield"),
                TranslatableField("test_emailfield"),  # Overriden!
                TranslatableField("test_slugfield"),
                SynchronizedField("test_urlfield"),
                TranslatableField("test_richtextfield"),
                TranslatableField("test_streamfield"),
                TranslatableField("test_snippet"),
                SynchronizedField("test_nontranslatablesnippet"),
                TranslatableField("test_customfield"),
                TranslatableField("test_translatable_childobjects"),
                SynchronizedField("test_nontranslatable_childobjects"),
            ],
        )


class TestCopySynchronisedFieldsWithManyToMany(TestCase):
    """Tests for copy_synchronised_fields with ManyToManyField."""

    def setUp(self):
        self.src_locale = Locale.get_default()
        self.dest_locale = Locale.objects.create(language_code="fr")

        # Create some NonTranslatableSnippet instances to use in M2M relations
        self.snippet1 = NonTranslatableSnippet.objects.create(field="Snippet 1")
        self.snippet2 = NonTranslatableSnippet.objects.create(field="Snippet 2")
        self.snippet3 = NonTranslatableSnippet.objects.create(field="Snippet 3")

    def test_m2m_field_is_synchronized_when_set_as_synchronized_field(self):
        """
        Test that ManyToManyField values are copied when the field is
        explicitly set as a SynchronizedField.
        """
        # Create source snippet with M2M relations
        source = TestM2MSnippet.objects.create(
            title="Source Snippet",
            locale=self.src_locale,
        )
        source.m2m_field.set([self.snippet1, self.snippet2])

        # Create target snippet (translation)
        target = TestM2MSnippet.objects.create(
            title="Target Snippet",
            locale=self.dest_locale,
            translation_key=source.translation_key,
        )

        # Verify target has no M2M relations initially
        self.assertEqual(target.m2m_field.count(), 0)

        # Copy synchronized fields
        copy_synchronised_fields(source, target)

        # Verify M2M relations were copied
        self.assertEqual(target.m2m_field.count(), 2)
        self.assertIn(self.snippet1, target.m2m_field.all())
        self.assertIn(self.snippet2, target.m2m_field.all())

    def test_m2m_field_sync_replaces_existing_relations(self):
        """
        Test that synchronizing M2M fields replaces existing relations
        on the target with those from the source.
        """
        source = TestM2MSnippet.objects.create(
            title="Source Snippet",
            locale=self.src_locale,
        )
        source.m2m_field.set([self.snippet1, self.snippet2])

        target = TestM2MSnippet.objects.create(
            title="Target Snippet",
            locale=self.dest_locale,
            translation_key=source.translation_key,
        )
        # Set different M2M relations on target
        target.m2m_field.set([self.snippet3])

        # Verify target has different relations
        self.assertEqual(target.m2m_field.count(), 1)
        self.assertIn(self.snippet3, target.m2m_field.all())

        # Copy synchronized fields
        copy_synchronised_fields(source, target)

        # Verify M2M relations were replaced with source's relations
        self.assertEqual(target.m2m_field.count(), 2)
        self.assertIn(self.snippet1, target.m2m_field.all())
        self.assertIn(self.snippet2, target.m2m_field.all())
        self.assertNotIn(self.snippet3, target.m2m_field.all())

    def test_m2m_field_sync_with_empty_source(self):
        """
        Test that synchronizing clears target M2M relations when source has none.
        """
        source = TestM2MSnippet.objects.create(
            title="Source Snippet",
            locale=self.src_locale,
        )
        # Source has no M2M relations

        target = TestM2MSnippet.objects.create(
            title="Target Snippet",
            locale=self.dest_locale,
            translation_key=source.translation_key,
        )
        target.m2m_field.set([self.snippet1, self.snippet2])

        # Verify target has relations
        self.assertEqual(target.m2m_field.count(), 2)

        # Copy synchronized fields
        copy_synchronised_fields(source, target)

        # Verify M2M relations were cleared
        self.assertEqual(target.m2m_field.count(), 0)
