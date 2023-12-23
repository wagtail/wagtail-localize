from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from wagtail.models import Locale, Page

from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.operations import TranslationCreator
from wagtail_localize.segments import RelatedObjectSegmentValue
from wagtail_localize.test.models import TestPage


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    page_revision = page.save_revision()
    page_revision.publish()
    page.refresh_from_db()

    source, created = TranslationSource.get_or_create_from_instance(page)
    prepare_source(source)

    return page


def prepare_source(source):
    # Recurse into any related objects
    for segment in source.relatedobjectsegment_set.all():
        if isinstance(segment, RelatedObjectSegmentValue):
            related_source, created = TranslationSource.get_or_create_from_instance(
                segment.get_instance(source.locale)
            )
            prepare_source(related_source)


class TranslationOperationsTest(TestCase):
    def setUp(self):
        # Create a Belarusian locale for testing
        self.be_locale = Locale.objects.create(language_code="be")

        # Create a test page
        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
        )

        # Create a user
        self.user = get_user_model().objects.create(username="testuser")

        # Instantiate TranslationCreator with the default and Belarusian locales for target_locales
        self.target_locales = [self.page.locale, self.be_locale]
        self.translation_creator = TranslationCreator(
            user=self.user, target_locales=self.target_locales
        )

        # Check if TranslationSource already exists
        source, created = TranslationSource.objects.get_or_create(
            object_id=self.page.translation_key,
            specific_content_type=ContentType.objects.get_for_model(TestPage),
            locale=self.page.locale,
        )

        # If not created, prepare the source
        if created:
            prepare_source(source)

    def test_create_translations_skips_duplicate(self):
        # Call create_translations() to check that only one translation has been created
        self.translation_creator.create_translations(self.page)

        # Assert statements for better readability
        self.assertEqual(
            TranslationSource.objects.filter(
                object_id=self.page.translation_key
            ).count(),
            1,
            "Only one TranslationSource should be created for the source page",
        )

        self.assertEqual(
            Translation.objects.filter(
                source__object_id=self.page.translation_key,
                target_locale=self.be_locale,
            ).count(),
            1,
            "Only one Translation object should be created for the Belarusian locale",
        )

        self.assertEqual(
            Translation.objects.filter(
                source__object_id=self.page.translation_key,
                target_locale=self.page.locale,
            ).count(),
            0,
            "No Translation object should be created for the default locale",
        )
