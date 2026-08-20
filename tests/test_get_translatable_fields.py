from django.conf import settings
from django.test import TestCase

from wagtail_localize.fields import (
    SynchronizedField,
    TranslatableField,
    get_translatable_fields,
)


if settings.USE_CUSTOM_PAGE_MODEL:
    from tests.testapp.testpages_custombasepage.models import (
        TestGenerateTranslatableFieldsPage,
        TestOverrideTranslatableFieldsPage,
    )
else:
    from tests.testapp.testpages_default.models import (
        TestGenerateTranslatableFieldsPage,
        TestOverrideTranslatableFieldsPage,
    )


class TestGetTranslatableFields(TestCase):
    def test(self):
        translatable_fields = get_translatable_fields(
            TestGenerateTranslatableFieldsPage
        )

        if settings.USE_CUSTOM_PAGE_MODEL:
            self.assertCountEqual(
                translatable_fields,
                [
                    TranslatableField("title"),
                    TranslatableField("slug"),
                    # no seo title, search description and show_in_menus fields on custom page model
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

        else:
            self.assertCountEqual(
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

        if settings.USE_CUSTOM_PAGE_MODEL:
            self.assertCountEqual(
                translatable_fields,
                [
                    TranslatableField("title"),
                    TranslatableField("slug"),
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
        else:
            self.assertCountEqual(
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
