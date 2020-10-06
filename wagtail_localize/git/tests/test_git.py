import tempfile
import os
from unittest import mock

import toml
import pygit2
from django.test import TestCase, override_settings

from wagtail_localize.git.git import Repository, RepositoryReader, RepositoryWriter

from .utils import GitRepositoryUtils


class GitTestCase(GitRepositoryUtils, TestCase):
    def setUp(self):
        super().setUp()
        self.repo_dir, self.repo = self.make_repo()
        self.repo_dir = tempfile.TemporaryDirectory()
        self.initial_commit = self.repo.gitpython.index.commit("initial commit")
        self.repo.gitpython.create_head("master")


class TestRepository(GitTestCase):
    def test_get_reader(self):
        reader = self.repo.reader()

        self.assertIsInstance(reader, RepositoryReader)

    def test_get_reader_for_empty_repo(self):
        self.repo.repo_is_empty = True
        reader = self.repo.reader()

        self.assertIsNone(reader)

    def test_get_writer(self):
        writer = self.repo.writer()

        self.assertIsInstance(writer, RepositoryWriter)

    def test_get_head_commit_id(self):
        commit_id = self.repo.get_head_commit_id()

        self.assertEqual(commit_id, self.initial_commit.hexsha)

    def test_get_head_commit_id_for_empty_repo(self):
        self.repo.repo_is_empty = True
        commit_id = self.repo.get_head_commit_id()

        self.assertIsNone(commit_id)


@mock.patch('pygit2.Repository')
@mock.patch('wagtail_localize.git.git.Repo')
class TestRepositoryClonePullPush(GitTestCase):
    def test_open(self, Repo, PyGitRepository):
        with override_settings(WAGTAILLOCALIZE_GIT_CLONE_DIR=self.repo_dir.name):
            Repository.open()

        Repo.clone_from.assert_not_called()

        PyGitRepository.assert_called_with(self.repo_dir.name)
        Repo.assert_called_with(self.repo_dir.name)

    def test_open_empty(self, Repo, PyGitRepository):
        empty_dir = tempfile.TemporaryDirectory()
        os.rmdir(empty_dir.name)
        with override_settings(WAGTAILLOCALIZE_GIT_CLONE_DIR=empty_dir.name, WAGTAILLOCALIZE_GIT_URL='git@github.com:wagtail/wagtail-localize.git'):
            Repository.open()

        Repo.clone_from.assert_called_with('git@github.com:wagtail/wagtail-localize.git', empty_dir.name, bare=True)

        PyGitRepository.assert_called_with(empty_dir.name)
        Repo.assert_called_with(empty_dir.name)

        empty_dir.cleanup()

    def test_pull(self, Repo, PyGitRepository):
        self.repo.gitpython = mock.MagicMock()
        self.repo.pygit = mock.MagicMock()
        self.repo.pygit.lookup_reference.return_value.target = '1234'

        self.repo.pull()

        self.repo.gitpython.remotes.origin.fetch.assert_called_with("+refs/heads/*:refs/remotes/origin/*")
        self.repo.pygit.lookup_reference.assert_called_with("refs/remotes/origin/master")
        self.repo.pygit.head.set_target.assert_called_with('1234')
        self.assertFalse(self.repo.repo_is_empty)

    def test_pull_empty(self, Repo, PyGitRepository):
        self.repo.gitpython = mock.MagicMock()
        self.repo.pygit = mock.MagicMock()
        self.repo.pygit.lookup_reference.side_effect = KeyError

        self.repo.pull()

        self.repo.gitpython.remotes.origin.fetch.assert_called_with("+refs/heads/*:refs/remotes/origin/*")
        self.repo.pygit.lookup_reference.assert_called_with("refs/remotes/origin/master")
        self.repo.pygit.head.set_target.assert_not_called()
        self.assertTrue(self.repo.repo_is_empty)

    def test_push(self, Repo, PyGitRepository):
        self.repo.gitpython = mock.MagicMock()
        self.repo.push()

        self.repo.gitpython.remotes.origin.push.assert_called_with(["refs/heads/master"])


class TestRepositoryGetChangedFiles(GitTestCase):
    def setUp(self):
        super().setUp()

        # Create a commit that creates some files to change
        index = pygit2.Index()
        self.add_file_to_index(self.repo, index, "locales/test.txt", "this is a test")
        self.add_file_to_index(self.repo, index, "locales/test-change.txt", "this is a test")
        self.add_file_to_index(self.repo, index, "test-change.txt", "this is a test")
        self.add_file_to_index(self.repo, index, "locales/test-delete.txt", "this is a test")
        self.first_commit_id = self.make_commit_from_index(self.repo, index, "First commit")

        # Create a second commit with some files changed:
        # test.txt remains the same
        # test-change.txt was changed
        # test-delete.txt was deleted
        # test-added.txt was added
        index = pygit2.Index()
        self.add_file_to_index(self.repo, index, "locales/test.txt", "this is a test")
        self.add_file_to_index(self.repo, index, "locales/test-change.txt", "this is a test that has been changed")
        self.add_file_to_index(self.repo, index, "test-change.txt", "this is a test that has been changed")
        self.add_file_to_index(self.repo, index, "locales/test-added.txt", "this is a test")
        self.second_commit_id = self.make_commit_from_index(self.repo, index, "Second commit")

    def test_get_changed_files(self):
        result = list(self.repo.get_changed_files(self.first_commit_id, self.second_commit_id))

        # Additions, deletes and any changes outside of 'locales/' should be ignored
        self.assertEqual(result, [
            ('locales/test-change.txt', b'this is a test', b'this is a test that has been changed')
        ])

    def test_get_changed_files_incorrect_commit_order(self):
        with self.assertRaises(ValueError) as e:
            list(self.repo.get_changed_files(self.second_commit_id, self.first_commit_id))

        self.assertEqual(e.exception.args, ('Second commit must be a descendant of first commit',))

    def test_get_changed_files_from_initial_commit(self):
        result = list(self.repo.get_changed_files(None, self.first_commit_id))

        # Everything should be ignored as it's all additions
        self.assertEqual(result, [])


class TestRepositoryReader(GitTestCase):
    def setUp(self):
        super().setUp()

        # Create a commit that creates some files to change
        index = pygit2.Index()
        self.add_file_to_index(self.repo, index, "test.txt", "this is a test")
        self.first_commit_id = self.make_commit_from_index(self.repo, index, "First commit")

    def test_read_file(self):
        reader = self.repo.reader()

        self.assertEqual(
            reader.read_file("test.txt"),
            b'this is a test'
        )

    def test_read_nonexistent_file(self):
        reader = self.repo.reader()

        with self.assertRaises(KeyError) as e:
            reader.read_file("foo.txt"),

        self.assertEqual(e.exception.args, ('foo.txt',))


class TestRepositoryWriter(GitTestCase):
    def test_write_file_and_commit(self):
        writer = self.repo.writer()

        writer.write_file("test.txt", "this is a test")
        writer.commit("Added test.txt")

        # Check new commit
        commit = self.repo.gitpython.head.commit
        self.assertEqual(commit.parents, (self.initial_commit,))
        self.assertEqual(commit.author.name, "Wagtail Localize")
        self.assertEqual(commit.author.email, "wagtail_localize_pontoon@wagtail.io")
        self.assertEqual(commit.message, "Added test.txt")

        # Check file has been committed
        def check_contents(contents):
            self.assertEqual(contents.decode(), "this is a test")

        self.assert_file_in_tree(commit.tree, "test.txt", check_contents=check_contents)

    def test_has_changes(self):
        writer = self.repo.writer()

        # Initially, should be no changes
        self.assertFalse(writer.has_changes())

        # Writing data should make it return True
        writer.write_file("test.txt", "this is a test")
        self.assertTrue(writer.has_changes())

        # After committing that change, should return False again
        writer.commit("Added test.txt")
        self.assertFalse(writer.has_changes())

        # Writing a file, but not changing anything should make it still return False
        writer.write_file("test.txt", "this is a test")
        self.assertFalse(writer.has_changes())

        # But making actual changes to the file should make it return True
        writer.write_file("test.txt", "this is an updated test")
        self.assertTrue(writer.has_changes())

    def test_has_changes_when_repo_empty(self):
        self.repo.repo_is_empty = True
        writer = self.repo.writer()

        # Always has changes if the repo is empty
        self.assertTrue(writer.has_changes())

    def test_write_config(self):
        writer = self.repo.writer()

        writer.write_config(
            ["en", "de", "fr"],
            [("templates/mytemplate.pot", "locales/de/mytranslation.po")],
        )

        writer.commit("Wrote config")

        # Check file has been committed
        def check_contents(contents):
            self.assertEqual(
                toml.loads(contents.decode()),
                {
                    "locales": ["en", "de", "fr"],
                    "paths": [
                        {
                            "l10n": "locales/de/mytranslation.po",
                            "reference": "templates/mytemplate.pot",
                        }
                    ],
                },
            )

        self.assert_file_in_tree(
            self.repo.gitpython.head.commit.tree, "l10n.toml", check_contents=check_contents
        )

    def test_copy_unmanaged_files(self):
        # Create some files
        index = pygit2.Index()
        self.add_file_to_index(self.repo, index, "locales/test.txt", "this file is managed because it's in locales")
        self.add_file_to_index(self.repo, index, "templates/test.txt", "this file is managed because it's in templates")
        self.add_file_to_index(self.repo, index, "l10n.toml", "this one is also managed")
        self.add_file_to_index(self.repo, index, "README.md", "this is an unmanaged file")
        self.add_file_to_index(self.repo, index, "docs/foo.md", "this is also an unmanaged file")
        self.make_commit_from_index(self.repo, index, "First commit")

        writer = self.repo.writer()
        writer.copy_unmanaged_files(self.repo.reader())
        writer.commit("Copied unmanaged files")

        # Checkunmanaged files were copied
        self.assert_file_in_tree(self.repo.gitpython.head.commit.tree, "README.md")
        # FIXME self.assert_file_in_tree(self.repo.gitpython.head.commit.tree, "docs/foo.md")

        # Check managed files weren't
        self.assert_file_not_in_tree(self.repo.gitpython.head.commit.tree, "locales/test.txt")
        self.assert_file_not_in_tree(self.repo.gitpython.head.commit.tree, "templates/test.txt")
        self.assert_file_not_in_tree(self.repo.gitpython.head.commit.tree, "l10n.toml")

    def test_commit(self):
        parent = self.repo.gitpython.head.commit

        writer = self.repo.writer()
        writer.commit("Commit")

        head_commit = self.repo.gitpython.head.commit
        self.assertEqual(head_commit.message, "Commit")
        self.assertEqual(head_commit.parents, (parent,))
        self.assertEqual(head_commit.author.name, "Wagtail Localize")
        self.assertEqual(head_commit.author.email, "wagtail_localize_pontoon@wagtail.io")

    def test_commit_empty_repo(self):
        # Set up a new empty repo
        repo_dir, repo = self.make_repo()

        # FIXME: This should be detected
        repo.repo_is_empty = True

        writer = repo.writer()
        writer.commit("Initial commit")

        head_commit = repo.gitpython.head.commit
        self.assertEqual(head_commit.message, "Initial commit")
        self.assertEqual(head_commit.parents, ())
        self.assertEqual(head_commit.author.name, "Wagtail Localize")
        self.assertEqual(head_commit.author.email, "wagtail_localize_pontoon@wagtail.io")
