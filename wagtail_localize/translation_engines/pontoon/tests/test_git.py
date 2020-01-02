import io
import tempfile

import toml
import pygit2
from django.test import TestCase
from git import Repo

from ..git import Repository


class GitTestCase(TestCase):
    def setUp(self):
        self.repo_dir = tempfile.TemporaryDirectory()
        self.gitpython = Repo.init(self.repo_dir.name, bare=True)
        self.initial_commit = self.gitpython.index.commit("initial commit")
        self.gitpython.create_head("master")
        self.pygit = pygit2.Repository(self.repo_dir.name)
        self.repo = Repository(self.pygit, self.gitpython)

    def assert_file_in_tree(self, tree, name, mode=33188, check_contents=None):
        # FIXME allow more than one file
        blob = tree.blobs[0]
        self.assertEqual(blob.name, name)
        self.assertEqual(blob.mode, mode)

        if check_contents is not None:
            contents = io.BytesIO()
            blob.stream_data(contents)
            check_contents(contents.getvalue())

    def tearDown(self):
        self.repo_dir.cleanup()


class TestRepositoryWriter(GitTestCase):
    def test_write_file_and_commit(self):
        writer = self.repo.writer()

        writer.write_file("test.txt", "this is a test")
        writer.commit("Added test.txt")

        # Check new commit
        commit = self.gitpython.head.commit
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

    def test_write_config(self):
        writer = self.repo.writer()

        writer.write_config(
            ["en", "de", "fr"],
            [("templates/mytemplate.pot", "locales/de/mytranslation.po"),],
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
            self.gitpython.head.commit.tree, "l10n.toml", check_contents=check_contents
        )
