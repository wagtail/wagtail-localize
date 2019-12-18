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

    def create_or_update_translated_page(self, submission, language):
        """
        Creates/updates the translated page to reflect the translations in translation memory.

        Note, all strings in the submission must be translated into the target language!
        """
        locale = Locale.objects.get(
            region_id=Region.objects.default_id(), language=language
        )

        page = submission.revision.page_revision.as_page_object()

        try:
            translated_page = page.get_translation(locale)
            created = False
        except page.specific_class.DoesNotExist:
            # May raise ParentNotTranslatedError
            translated_page = page.copy_for_translation(locale)
            created = True

        # Fetch all translated segments
        segment_locations = SegmentLocation.objects.filter(
            revision=submission.revision
        ).annotate_translation(language)

        template_locations = TemplateLocation.objects.filter(
            revision=submission.revision
        ).select_related("template")

        segments = []

        for page_location in segment_locations:
            segment = SegmentValue.from_html(
                page_location.path, page_location.translation
            )
            if page_location.html_attrs:
                segment.replace_html_attrs(json.loads(page_location.html_attrs))

            segments.append(segment)

        for page_location in template_locations:
            template = page_location.template
            segment = TemplateValue(
                page_location.path,
                template.template_format,
                template.template,
                template.segment_count,
            )
            segments.append(segment)

        # Ingest all translated segments into page
        ingest_segments(page, translated_page, page.locale.language, language, segments)

        # Make sure the slug is valid
        translated_page.slug = slugify(translated_page.slug)
        translated_page.save()

        new_revision = translated_page.save_revision()
        new_revision.publish()

        PontoonResourceTranslation.objects.create(
            submission=submission, language=language
        )

        return new_revision, created

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
            self.logger.info(
                f"Saving translation for '{resource.path}' in {language.get_display_name()}"
            )

            try:
                revision, created = self.create_or_update_translated_page(
                    translatable_submission, language
                )
            except ParentNotTranslatedError:
                # These pages will be handled when the parent is created in the code below
                self.logger.info(
                    f"Cannot save translation for '{resource.path}' in {language.get_display_name()} yet as its parent must be translated first"
                )
                return

            if created and translatable_submission.revision.page_revision is not None:
                source_page = translatable_submission.revision.page_revision.page

                # Check if this page has any children that may be ready to translate
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
