import os
import io
import tempfile

import pygit2
from django.test import override_settings
from git import Repo

from wagtail_localize.git.git import Repository


class GitRepositoryUtils:
    def setUp(self):
        self.dirs_to_cleanup = []
        super().setUp()

    def tearDown(self):
        for temp_dir in self.dirs_to_cleanup:
            temp_dir.cleanup()

    def make_repo(self):
        """
        Makes a new repo in a temporary directory
        """
        repo_dir = tempfile.TemporaryDirectory()
        self.dirs_to_cleanup.append(repo_dir)

        gitpython = Repo.init(repo_dir.name, bare=True)
        pygit = pygit2.Repository(repo_dir.name)

        return repo_dir.name, Repository(pygit, gitpython)

    def clone_repo(self, remote_repo_dir):
        """
        Clones the repo in the given directory into a new temporary directory
        """
        repo_dir = tempfile.TemporaryDirectory()
        self.dirs_to_cleanup.append(repo_dir)

        os.rmdir(repo_dir.name)

        with override_settings(
            WAGTAILLOCALIZE_GIT_CLONE_DIR=repo_dir.name,
            WAGTAILLOCALIZE_GIT_URL=remote_repo_dir,
        ):
            return repo_dir.name, Repository.open()

    def add_file_to_index(self, repo, index, filename, contents):
        blob = repo.pygit.create_blob(contents)
        index.add(pygit2.IndexEntry(filename, blob, pygit2.GIT_FILEMODE_BLOB))

    def make_commit_from_index(self, repo, index, message):
        tree = index.write_tree(repo.pygit)

        sig = pygit2.Signature(
            "Wagtail Localize", "wagtail_localize_pontoon@wagtail.io"
        )

        repo.pygit.create_commit(
            "refs/heads/master", sig, sig, message, tree, [repo.pygit.head.target]
        )

        return repo.pygit.head.target.hex

    def assert_file_in_tree(self, tree, name, mode=33188, check_contents=None):
        blobs_by_name = {
            blob.name: blob
            for blob in tree.blobs
        }

        self.assertIn(name, blobs_by_name)

        blob = blobs_by_name[name]
        self.assertEqual(blob.mode, mode)

        if check_contents is not None:
            contents = io.BytesIO()
            blob.stream_data(contents)
            check_contents(contents.getvalue())

    def assert_file_not_in_tree(self, tree, name):
        blobs_by_name = {
            blob.name: blob
            for blob in tree.blobs
        }

        self.assertNotIn(name, blobs_by_name)
