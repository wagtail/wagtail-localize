import tempfile
import uuid

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
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


class MakeAuthorsTranslatableMigrationTestCase(TransactionTestCase):
    """
    Check that migration 0004 works on a database that already has authors.

    The rows are created with the models as they were at 0003 and read back
    with the models at 0004, so what gets tested is the migration itself.
    """

    BEFORE = [("blog", "0003_alter_blogpage_body")]
    AFTER = [("blog", "0004_blogpersonrelationship_locale_and_more")]

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        call_command("migrate", "blog", verbosity=0)

    def make_authors(self, apps):
        """
        Create a post with three authors, using the models as they were at 0003.
        """
        ContentType = apps.get_model("contenttypes", "ContentType")
        HistoricLocale = apps.get_model("wagtailcore", "Locale")
        HistoricBlogPage = apps.get_model("blog", "BlogPage")
        HistoricPerson = apps.get_model("blog", "Person")
        HistoricRelationship = apps.get_model("blog", "BlogPersonRelationship")

        locale, _ = HistoricLocale.objects.get_or_create(language_code="en")
        content_type, _ = ContentType.objects.get_or_create(
            app_label="blog", model="blogpage"
        )

        post = HistoricBlogPage.objects.create(
            title="Post",
            draft_title="Post",
            slug="post-migration",
            path="900100010001",
            depth=3,
            numchild=0,
            url_path="/post-migration/",
            content_type=content_type,
            locale=locale,
            translation_key=uuid.uuid4(),
            introduction="",
            body="[]",
            subtitle="",
        )

        people = [
            HistoricPerson.objects.create(
                first_name=f"First {number}",
                last_name=f"Last {number}",
                job_title="Baker",
            )
            for number in range(3)
        ]

        relationships = [
            HistoricRelationship.objects.create(
                page=post, person=person, sort_order=number
            )
            for number, person in enumerate(people)
        ]

        return post, people, relationships

    def test_existing_authors_survive_and_get_a_key_each(self):
        old_apps = self.migrate(self.BEFORE)
        post, people, relationships = self.make_authors(old_apps)

        expected_people = {
            (person.first_name, person.last_name, person.job_title) for person in people
        }
        expected_links = {
            (relationship.person_id, relationship.page_id)
            for relationship in relationships
        }

        new_apps = self.migrate(self.AFTER)

        Person = new_apps.get_model("blog", "Person")
        Relationship = new_apps.get_model("blog", "BlogPersonRelationship")
        HistoricLocale = new_apps.get_model("wagtailcore", "Locale")

        migrated_people = list(Person.objects.all())
        migrated_links = list(Relationship.objects.all())

        # Nothing is dropped.
        self.assertEqual(len(migrated_people), 3)
        self.assertEqual(len(migrated_links), 3)

        # The rows still say what they said.
        self.assertEqual(
            {
                (person.first_name, person.last_name, person.job_title)
                for person in migrated_people
            },
            expected_people,
        )

        # And each relationship still points at the same author and post.
        self.assertEqual(
            {(link.person_id, link.page_id) for link in migrated_links},
            expected_links,
        )

        # Each row has a key of its own, which is what lets the constraint
        # exist at all.
        self.assertEqual(len({person.translation_key for person in migrated_people}), 3)
        self.assertEqual(len({link.translation_key for link in migrated_links}), 3)

        # They are all in the site's own language.
        english = HistoricLocale.objects.get(language_code="en")
        self.assertEqual({person.locale_id for person in migrated_people}, {english.pk})
        self.assertEqual({link.locale_id for link in migrated_links}, {english.pk})

        # The uniqueness is really in place on both models, not just declared.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Person.objects.create(
                first_name="Duplicate",
                last_name="Key",
                job_title="Baker",
                locale_id=english.pk,
                translation_key=migrated_people[0].translation_key,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Relationship.objects.create(
                page_id=migrated_links[0].page_id,
                person_id=migrated_links[0].person_id,
                sort_order=99,
                locale_id=english.pk,
                translation_key=migrated_links[0].translation_key,
            )
