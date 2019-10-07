from django.db import models, transaction
from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from wagtail.core.models import Page, PageRevision

from wagtail_localize.models import Language
from wagtail_localize.segments import SegmentValue, TemplateValue
from wagtail_localize.segments.ingest import ingest_segments

from .models import (
    Segment,
    SegmentTranslation,
    SegmentPageLocation,
    TemplatePageLocation,
)
from .utils import get_translation_progress


@transaction.atomic
def handle_completed_revision(revision_id, src_lang, tgt_lang):
    original_page = Page.objects.get(revisions__id=revision_id).specific

    # TODO: Not currently handling edited page translations
    if original_page.has_translation(tgt_lang):
        return

    original_page_at_revision = original_page.revisions.get(
        id=revision_id
    ).as_page_object()
    translated_page = original_page_at_revision.copy_for_translation(tgt_lang)

    # If the page doesn't yet have a translated parent, don't import it yet
    # This function will be called again when the translated parent is created
    if not translated_page:
        return

    # Fetch all translated segments
    segment_page_locations = SegmentPageLocation.objects.filter(
        page_revision_id=revision_id
    ).annotate_translation(tgt_lang)

    template_page_locations = TemplatePageLocation.objects.filter(
        page_revision_id=revision_id
    ).select_related("template")

    segments = []

    for page_location in segment_page_locations:
        segment = SegmentValue(page_location.path, page_location.translation)
        segments.append(segment)

    for page_location in template_page_locations:
        template = page_location.template
        segment = TemplateValue(
            page_location.path,
            template.template_format,
            template.template,
            template.segment_count,
        )
        segments.append(segment)

    ingest_segments(
        original_page_at_revision, translated_page, src_lang, tgt_lang, segments
    )

    translated_page.slug = slugify(translated_page.slug)

    translated_page.save()

    # Create initial revision
    translated_page.save_revision(changed=False)

    # As we created a new page, check to see if there are any child pages that
    # have complete translations as well. This can happen if the child pages
    # were translated before the parent.

    # Check all page revisions of children of the original page that have
    # been submitted for localisation
    child_page_revision_ids = PageRevision.objects.filter(
        page__in=original_page.get_children()
    ).values_list("id", flat=True)
    submitted_page_revision_ids = SegmentPageLocation.objects.values_list(
        "page_revision_id", flat=True
    )
    page_revision_ids_to_check = child_page_revision_ids.intersection(
        submitted_page_revision_ids
    )

    for page_revision_id in page_revision_ids_to_check:
        total_segments, translated_segments = get_translation_progress(
            page_revision_id, tgt_lang
        )

        if total_segments == translated_segments:
            # Page revision is now complete
            handle_completed_revision(page_revision_id, src_lang, tgt_lang)


@receiver(post_save, sender=SegmentTranslation)
def on_new_segment_translation(sender, instance, created, **kwargs):
    if created:
        segment_page_locations = SegmentPageLocation.objects.filter(
            segment_id=instance.translation_of_id
        )

        # Check if any translated pages can now be created
        for page_revision_id in segment_page_locations.values_list(
            "page_revision_id", flat=True
        ):
            total_segments, translated_segments = get_translation_progress(
                page_revision_id, instance.locale.language
            )

            if total_segments == translated_segments:
                # FIXME
                src_lang = Language.default()

                # Page revision is now complete
                handle_completed_revision(
                    page_revision_id, src_lang, instance.locale.language
                )


@transaction.atomic
def ingest_translations(src_lang, tgt_lang, translations):
    for source, translation in translations:
        segment = Segment.from_text(src_lang, source)
        SegmentTranslation.from_text(segment, tgt_lang, translation)
