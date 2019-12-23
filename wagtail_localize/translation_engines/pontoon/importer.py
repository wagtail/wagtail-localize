import json

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
import polib

from wagtail.core.models import Page
from wagtail_localize.models import (
    Locale,
    Region,
    ParentNotTranslatedError,
    TranslatablePageMixin,
)
from wagtail_localize.segments import SegmentValue, TemplateValue
from wagtail_localize.segments.ingest import ingest_segments
from wagtail_localize.translation_memory.models import (
    Segment,
    SegmentLocation,
    TemplateLocation,
)

from .models import (
    PontoonResource,
    PontoonResourceTranslation,
    PontoonSyncLog,
    PontoonSyncLogResource,
)


class Importer:
    def __init__(self, source_language, logger):
        self.source_language = source_language
        self.logger = logger
        self.log = None

    def import_resource(self, resource, language, old_po, new_po):
        for changed_entry in set(new_po) - set(old_po):
            try:
                segment = Segment.objects.get(
                    language=self.source_language, text=changed_entry.msgid
                )
                translation, created = segment.translations.get_or_create(
                    language=language,
                    defaults={
                        "text": changed_entry.msgstr,
                        "updated_at": timezone.now(),
                    },
                )

                if not created:
                    # Update the translation only if the text has changed
                    if translation.text != changed_entry.msgstr:
                        translation.text = changed_entry.msgstr
                        translation.updated_at = timezone.now()
                        translation.save()

            except Segment.DoesNotExist:
                self.logger.warning(f"Unrecognised segment '{changed_entry.msgid}'")

    def try_update_resource_translation(self, resource, language):
        # Check if there is a submission ready to be translated
        translatable_submission = resource.find_translatable_submission(language)

        if translatable_submission:
            locale = Locale.objects.get(
                region_id=Region.objects.default_id(), language=language
            )

            for dependency in translatable_submission.get_dependencies():
                if not dependency.object.has_translation(locale):
                    self.logger.info(
                        f"Can't translate '{resource.path}' into {language.get_display_name()} because its dependency '{dependency.path}' hasn't been translated yet"
                    )
                    return

            self.logger.info(
                f"Saving translation for '{resource.path}' in {language.get_display_name()}"
            )

            try:
                (
                    translation,
                    created,
                ) = translatable_submission.revision.create_or_update_translation(
                    locale
                )

                PontoonResourceTranslation.objects.create(
                    submission=translatable_submission, language=language
                )
            except ParentNotTranslatedError:
                # These pages will be handled when the parent is created in the code below
                self.logger.info(
                    f"Cannot save translation for '{resource.path}' in {language.get_display_name()} yet as its parent must be translated first"
                )
                return

            if created:
                # The translation was created.

                # The logic in this part checks to find any other submissions that were waiting
                # for this object to be translated first and triggers them to be translated as
                # well.

                # Look for any submissions that were waiting for this object to be translated.
                # For example, any linked snippets, images, etc must be translated before
                # the page. So if a page (the dependee) is ready to be translated and its last
                # linked item has just been translated, we can translate that page now.
                for dependee in resource.get_dependees():
                    # Check that the next translatable submission of the dependee resource is
                    # the dependee submission that's linked to this resource.
                    # This prevents us from translating an old submission that's been replaced.
                    if (
                        dependee.resource.find_translatable_submission(language)
                        != dependee
                    ):
                        continue

                    # FIXME: Could we pass in the translatable submission instead?
                    self.try_update_resource_translation(dependee.resource, language)

                # If a page was created, check to see if it has any children that are
                # now ready to translate.
                if translatable_submission.revision.page_revision is not None:
                    source_page = translatable_submission.revision.page_revision.page

                    child_page_resources = PontoonResource.objects.filter(
                        object__translation_key__in=[
                            child.translation_key
                            for child in source_page.get_children().specific()
                            if isinstance(child, TranslatablePageMixin)
                        ]
                    )

                    for resource in child_page_resources:
                        self.try_update_resource_translation(resource, language)

    def start_import(self, commit_id):
        self.log = PontoonSyncLog.objects.create(
            action=PontoonSyncLog.ACTION_PULL, commit_id=commit_id
        )

    def import_file(self, filename, old_content, new_content):
        self.logger.info(f"Pull: Importing changes in file '{filename}'")
        resource, language = PontoonResource.get_by_po_filename(filename)

        # Log that this resource was updated
        PontoonSyncLogResource.objects.create(
            log=self.log, resource=resource, language=language
        )

        old_po = polib.pofile(old_content.decode("utf-8"))
        new_po = polib.pofile(new_content.decode("utf-8"))

        self.import_resource(resource, language, old_po, new_po)

        # Check if the translated page is ready to be created/updated
        self.try_update_resource_translation(resource, language)
