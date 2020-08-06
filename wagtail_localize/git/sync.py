import logging
from pathlib import PurePosixPath

import polib
from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string
from wagtail.core.models import Locale

from wagtail_localize.models import Translation

from .git import Repository
from .models import SyncLog, Resource
from .importer import Importer


@transaction.atomic
def _pull(repo, logger):
    # Get the last commit ID that we either pulled or pushed
    last_log = SyncLog.objects.order_by("-time").exclude(commit_id="").first()
    last_commit_id = None
    if last_log is not None:
        last_commit_id = last_log.commit_id

    current_commit_id = repo.get_head_commit_id()

    if last_commit_id == current_commit_id:
        logger.info("Pull: No changes since last sync")
        return

    importer = Importer(current_commit_id, logger)
    for filename, old_content, new_content in repo.get_changed_files(
        last_commit_id, repo.get_head_commit_id()
    ):
        logger.info(f"Pull: Importing changes in file '{filename}'")
        po = polib.pofile(new_content.decode("utf-8"))
        translation = Translation.objects.get(uuid=po.metadata['X-WagtailLocalize-TranslationID'])
        importer.import_resource(translation, po)


def po_filename_for_object(resource, target_locale=None):
    """
    Returns the filename of this resource within the git repository that is shared with Pontoon.

    If a target_locale is specified, the filename for that locale is returned. Otherwise, the filename
    of the template is returned.
    """
    if target_locale is not None:
        base_path = PurePosixPath(
            f"locales/{target_locale.language_code}"  # TODO: as_rfc5646_language_tag
        )
    else:
        base_path = PurePosixPath("templates")

    return (base_path / str(resource.path)).with_suffix(".pot" if target_locale is None else ".po")


def locale_po_filename_template_for_object(resource):
    """
    Returns the template used for language-specific files for this resource.

    This value is passed to Pontoon in the configuration so it can find the language-specific files.
    """
    return (PurePosixPath("locales/{locale}") / str(resource.path)).with_suffix(".po")


@transaction.atomic
def _push(repo, logger):
    reader = repo.reader()
    writer = repo.writer()

    # Note: Reader is None on initial commit
    if reader:
        writer.copy_unmanaged_files(reader)

    def update_po(filename, new_po):
        if reader is not None:
            try:
                current_po_string = reader.read_file(filename).decode("utf-8")
            except KeyError:
                pass
            else:
                current_po = polib.pofile(current_po_string, wrapwidth=200)

                # Take metadata from existing PO file
                translation_id = new_po.metadata.get('X-WagtailLocalize-TranslationID')
                new_po.metadata = current_po.metadata
                if translation_id:
                    new_po.metadata['X-WagtailLocalize-TranslationID'] = translation_id

        writer.write_file(filename, str(new_po))

    source_locale = Locale.get_default()
    target_locales = Locale.objects.exclude(
        id=source_locale.id
    )

    paths = []
    for translation in (
        Translation.objects.filter(source__locale=source_locale, target_locale__in=target_locales)
        .select_related("source")
    ):
        resource = Resource.get_for_object(translation.source.object)

        source_po = translation.source.export_po()
        source_po_filename = po_filename_for_object(resource)
        update_po(str(source_po_filename), source_po)

        locale_po = translation.export_po()
        update_po(
            str(po_filename_for_object(resource, target_locale=translation.target_locale)), locale_po
        )

        paths.append(
            (
                source_po_filename,
                locale_po_filename_template_for_object(resource)
            )
        )

    writer.write_config(
        [locale.language_code for locale in target_locales], paths  # TODO as_rfc5646_language_tag
    )

    if writer.has_changes():
        previous_commit = repo.get_head_commit_id()

        # Create a new log for this push
        log = SyncLog.objects.create(
            action=SyncLog.ACTION_PUSH, commit_id=""
        )

        logger.info("Push: Committing changes")
        log.commit_id = writer.commit("Updates to source content")
        log.save(update_fields=["commit_id"])
        repo.push()

        # Add any resources that have changed to the log
        # This ignores any deletions since we don't care about those
        for filename, old_content, new_content in repo.get_changed_files(previous_commit, log.commit_id):
            # Note: get_changed_files only picks up changes in the locales/ folder so we can assume they're all PO
            # files and they have a Translation ID
            # (anything else that gets in there won't be written into the new commit so, effectively, they get deleted)
            po = polib.pofile(new_content.decode("utf-8"))
            translation = Translation.objects.get(uuid=po.metadata['X-WagtailLocalize-TranslationID'])
            log.add_translation(translation)

    else:
        logger.info(
            "Push: Not committing anything as recent changes haven't affected any translatable content"
        )


class SyncManager:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def sync(self):
        self.logger.info("Pulling repository")
        repo = Repository.open()
        repo.pull()

        _pull(repo, self.logger)
        _push(repo, self.logger)

        self.logger.info("Finished")

    def trigger(self):
        """
        Called when user presses the "Sync" button in the admin

        This should enqueue a background task to run the sync() function
        """
        self.sync()

    def is_queued(self):
        """
        Returns True if the background task is queued
        """
        return False

    def is_running(self):
        """
        Returns True if the background task is currently running
        """
        return False


def get_sync_manager():
    sync_manager_class_path = getattr(
        settings,
        "WAGTAILLOCALIZE_GIT_SYNC_MANAGER_CLASS",
        "wagtail_localize_pontoon.sync.SyncManager",
    )
    sync_manager = import_string(sync_manager_class_path)
    return sync_manager()
