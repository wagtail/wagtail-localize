import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.models import Locale, Page
from wagtail.test.utils import WagtailPageTestCase

from blog.models import BlogIndexPage, BlogPage, Person
from wagtail_localize.fields import (
    SynchronizedField,
    TranslatableField,
    get_translatable_fields,
)
from wagtail_localize.models import Translation, TranslationSource


def translatable_fields_by_name(model):
    return {field.field_name: field for field in get_translatable_fields(model)}


def translate(instance, locale):
    """
    Translate `instance` into `locale` and publish it, leaving every string segment
    untranslated. These are the steps the admin runs when an editor submits an object
    for translation and publishes it.
    """
    source, _created = TranslationSource.get_or_create_from_instance(instance)
    translation, _created = Translation.objects.get_or_create(
        source=source, target_locale=locale
    )
    translation.save_target(publish=True)
    return translation


class PersonTranslatableFieldsTests(TestCase):
    """
    Tests for how the author snippet's fields are translated.
    """

    def test_job_title_is_translatable(self):
        fields = translatable_fields_by_name(Person)
        self.assertIsInstance(fields["job_title"], TranslatableField)

    def test_names_are_synchronised(self):
        fields = translatable_fields_by_name(Person)
        self.assertIsInstance(fields["first_name"], SynchronizedField)
        self.assertIsInstance(fields["last_name"], SynchronizedField)


class BlogPageTranslatableFieldsTests(TestCase):
    """
    Tests for how a blog post's link to its authors is translated.
    """

    def test_author_relationship_is_translatable(self):
        fields = translatable_fields_by_name(BlogPage)
        self.assertIsInstance(
            fields["blog_person_relationship"],
            TranslatableField,
        )


class TranslatedAuthorTests(WagtailPageTestCase):
    """
    Tests that a translated post links to the author in its own language.
    """

    def setUp(self):
        self.french = Locale.objects.create(language_code="fr")

        root_page = Page.get_first_root_node()
        self.en_blog_index = BlogIndexPage(title="Blog")
        root_page.add_child(instance=self.en_blog_index)

        self.en_author = Person.objects.create(
            first_name="Olivia",
            last_name="Ava",
            job_title="Director",
        )

        self.en_post = BlogPage(title="Bread and Circuses")
        self.en_blog_index.add_child(instance=self.en_post)
        self.en_post.blog_person_relationship.create(person=self.en_author)
        self.en_post.save()

    def test_translated_post_links_to_the_translated_author(self):
        # The author is translated first, so that the post's translation can link to it.
        translate(self.en_author, self.french)
        translate(self.en_post, self.french)

        french_post = self.en_post.get_translation(self.french)
        french_author = self.en_author.get_translation(self.french)

        self.assertEqual(french_post.authors(), [french_author])


class LoadInitialDataTests(TestCase):
    """
    Tests for the command that builds the demo's content.
    """

    def setUp(self):
        # The command writes the fixture images, which belong in a throwaway directory.
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_root = override_settings(MEDIA_ROOT=media.name)
        media_root.enable()
        self.addCleanup(media_root.disable)

    def test_it_publishes_a_french_post_with_a_french_author(self):
        # Translated pages are published from an on_commit callback, which a TestCase
        # transaction never reaches on its own.
        with self.captureOnCommitCallbacks(execute=True):
            call_command("load_initial_data", verbosity=0)

        french = Locale.objects.get(language_code="fr")
        french_post = BlogPage.objects.get(locale=french)

        self.assertTrue(french_post.live)
        self.assertEqual(french_post.authors()[0].locale, french)
