import sys
import unittest
from unittest import mock
from pathlib import PurePosixPath

import pygit2
from django.test import TestCase
from wagtail.core.models import Page, Locale

from wagtail_localize.models import TranslationSource, Translation, StringTranslation
from wagtail_localize.test.models import TestPage

from wagtail_localize.git.models import SyncLog, Resource
from wagtail_localize.git.sync import _push, _pull

from .utils import GitRepositoryUtils


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    source, created = TranslationSource.get_or_create_from_instance(page)
    return page, source


class TestPull(GitRepositoryUtils, TestCase):
    def setUp(self):
        super().setUp()

        self.locale_en = Locale.objects.get(language_code="en")
        self.locale_fr = Locale.objects.create(language_code="fr")

    def make_test_resource(self):
        # Set up a test translation
        page, source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some test translatable content",
        )
        translation = Translation.objects.create(
            source=source,
            target_locale=self.locale_fr,
        )
        resource = Resource.get_for_object(source.object)

        return page, source, translation, resource

    def make_test_repo(self):
        repo_dir, repo = self.make_repo()
        repo.gitpython.index.commit("Initial commit")
        repo.gitpython.create_head("master")
        return repo

    def commit_translation(self, repo, resource, translation, modify_locale_po=None, commit_message=None):
        translation_po = translation.export_po()

        if modify_locale_po:
            modify_locale_po(translation_po)

        index = pygit2.Index()
        self.add_file_to_index(repo, index, f"templates/{resource.path}.pot", str(translation.source.export_po()))
        self.add_file_to_index(repo, index, f"locales/fr/{resource.path}.po", str(translation_po))
        return self.make_commit_from_index(repo, index, commit_message or "Added a translation")

    def test_pull(self):
        page, source, translation, resource = self.make_test_resource()

        # Set up repo
        repo = self.make_test_repo()

        # page into repo and commit
        push_commit_id = self.commit_translation(repo, resource, translation)

        # Add a SyncLog entry
        # Wagtail uses the synclog to know when to detect changes from
        SyncLog.objects.create(action=SyncLog.ACTION_PUSH, commit_id=push_commit_id)

        # Let's simulate Pontoon modifying the git repo
        def add_french_string(translation_po):
            translation_po[0].msgstr = "Certains tests de contenu traduisible"
        pontoon_commit_id = self.commit_translation(repo, resource, translation, modify_locale_po=add_french_string, commit_message="(Pontoon) Edited a translation")

        # Run the pull code
        logger = mock.MagicMock()
        _pull(repo, logger)

        # Check a new sync log was created
        sync_log = SyncLog.objects.get(action=SyncLog.ACTION_PULL)
        self.assertEqual(sync_log.commit_id, pontoon_commit_id)

        # Check the translated string was inserted
        string_translation = StringTranslation.objects.get()
        self.assertEqual(string_translation.translation_of.data, "Some test translatable content")
        self.assertEqual(string_translation.locale, self.locale_fr)
        self.assertEqual(string_translation.context.object, source.object)
        self.assertEqual(string_translation.context.path, 'test_charfield')
        self.assertEqual(string_translation.data, "Certains tests de contenu traduisible")
        self.assertEqual(string_translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(string_translation.tool_name, "Pontoon")
        self.assertFalse(string_translation.has_error)

    def test_pull_with_string_error(self):
        page, source, translation, resource = self.make_test_resource()

        # Set up repo
        repo = self.make_test_repo()

        # page into repo and commit
        push_commit_id = self.commit_translation(repo, resource, translation)

        # Add a SyncLog entry
        # Wagtail uses the synclog to know when to detect changes from
        SyncLog.objects.create(action=SyncLog.ACTION_PUSH, commit_id=push_commit_id)

        # Let's simulate Pontoon modifying the git repo
        # This time, we will insert invalid HTML
        def add_french_string(translation_po):
            translation_po[0].msgstr = "<script>foo()</script>"
        pontoon_commit_id = self.commit_translation(repo, resource, translation, modify_locale_po=add_french_string, commit_message="(Pontoon) Edited a translation")

        # Run the pull code
        logger = mock.MagicMock()
        _pull(repo, logger)

        # Check a new sync log was created
        sync_log = SyncLog.objects.get(action=SyncLog.ACTION_PULL)
        self.assertEqual(sync_log.commit_id, pontoon_commit_id)

        # Check the translated string was inserted, but the error was detected
        string_translation = StringTranslation.objects.get()
        self.assertEqual(string_translation.translation_of.data, "Some test translatable content")
        self.assertEqual(string_translation.data, "<script>foo()</script>")
        self.assertEqual(string_translation.translation_type, StringTranslation.TRANSLATION_TYPE_MANUAL)
        self.assertEqual(string_translation.tool_name, "Pontoon")
        self.assertTrue(string_translation.has_error)

    def test_pull_without_changes(self):
        page, source, translation, resource = self.make_test_resource()

        # Set up repo
        repo = self.make_test_repo()

        # page into repo and commit
        push_commit_id = self.commit_translation(repo, resource, translation)

        # Add a SyncLog entry
        # Wagtail uses the synclog to know when to detect changes from
        SyncLog.objects.create(action=SyncLog.ACTION_PUSH, commit_id=push_commit_id)

        # Run the pull code
        logger = mock.MagicMock()
        _pull(repo, logger)

        # No sync log should've been created
        self.assertFalse(SyncLog.objects.filter(action=SyncLog.ACTION_PULL).exists())

    @unittest.expectedFailure
    def test_pull_empty_repo(self):
        # Set up remote repos
        remote_repo_dir, remote_repo = self.make_repo()
        local_repo_dir, local_repo = self.clone_repo(remote_repo_dir)

        logger = mock.MagicMock()

        _pull(local_repo, logger)


class TestPush(TestCase):
    def setUp(self):
        self.locale_en = Locale.objects.get(language_code="en")
        self.locale_fr = Locale.objects.create(language_code="fr")

    def test_empty_push(self):
        repo = mock.MagicMock()
        logger = mock.MagicMock()

        repo.reader().read_file.side_effect = KeyError
        repo.get_head_commit_id.return_value = "0" * 40
        repo.writer().commit.return_value = "1" * 40

        _push(repo, logger)

        # Check that config was written
        # French language should be configured, no pages should be submitted
        repo.writer().write_config.assert_called_once_with(["fr"], [])

        # Check that no pages were written
        repo.writer().write_file.assert_not_called()

        # Check that the repo was pushed
        repo.push.assert_called_once()

        # Check log
        log = SyncLog.objects.get()
        self.assertEqual(log.action, SyncLog.ACTION_PUSH)
        self.assertTrue(log.time)
        self.assertTrue(log.commit_id, "1" * 40)
        self.assertFalse(log.resources.exists())

    def test_push_something(self):
        page, source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some test translatable content",
        )
        Translation.objects.create(
            source=source,
            target_locale=self.locale_fr,
        )

        repo = mock.MagicMock()
        logger = mock.MagicMock()

        repo.reader().read_file.side_effect = KeyError
        repo.get_head_commit_id.return_value = "0" * 40
        repo.writer().commit.return_value = "1" * 40

        _push(repo, logger)

        # Check that the config was written
        repo.writer().write_config.assert_called_once_with(
            ["fr"],
            [
                (
                    PurePosixPath("templates/pages/test-page.pot"),
                    PurePosixPath(r"locales/{locale}/pages/test-page.po"),
                )
            ],
        )

        repo.get_changed_files.assert_called_once_with("0" * 40, "1" * 40)

        # Check that the source and translation files were written
        # Build a dictionary of calls to RepositoryWriter.write_file(). Keyed by first argument (filename)
        # Note, this check only works on Python 3.8+
        if sys.version_info >= (3, 8):
            mock_calls = {
                call.args[0]: call for call in repo.writer().write_file.mock_calls
            }

            self.assertIn("templates/pages/test-page.pot", mock_calls.keys())
            self.assertIn("locales/fr/pages/test-page.po", mock_calls.keys())

        # Check that the repo was pushed
        repo.push.assert_called_once()

        # Check log
        log = SyncLog.objects.get()
        self.assertEqual(log.action, SyncLog.ACTION_PUSH)
        self.assertTrue(log.time)
        self.assertTrue(log.commit_id, "1" * 40)

        # FIXME: Need to properly mock out repo.get_changed_files to test this properly
        self.assertFalse(log.resources.exists())
