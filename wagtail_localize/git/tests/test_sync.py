import sys
from unittest import mock
from pathlib import PurePosixPath

from django.test import TestCase
from wagtail.core.models import Page, Locale

from wagtail_localize.models import TranslationSource, Translation
from wagtail_localize.test.models import TestPage

from wagtail_localize.git.models import SyncLog
from wagtail_localize.git.sync import _push


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    source, created = TranslationSource.get_or_create_from_instance(page)
    return page, source


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
