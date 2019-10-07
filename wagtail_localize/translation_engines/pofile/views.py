import tempfile
from collections import defaultdict

import polib
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify

from wagtail_localize.admin.workflow.models import TranslationRequest
from wagtail_localize.segments import SegmentValue, TemplateValue
from wagtail_localize.segments.extract import extract_segments
from wagtail_localize.segments.ingest import ingest_segments


@require_GET
def download(request, translation_request_id):
    translation_request = get_object_or_404(
        TranslationRequest, id=translation_request_id
    )

    # Extract messages from pages
    messages = defaultdict(list)
    for page in translation_request.pages.all():
        instance = page.source_revision.as_page_object()

        segments = extract_segments(instance)

        # Filter out templates
        text_segments = [
            segment for segment in segments if isinstance(segment, SegmentValue)
        ]

        for segment in text_segments:
            messages[segment.text].append((instance.url_path, segment.path))

    # Build a PO file
    po = polib.POFile()
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
    }

    for text, occurances in messages.items():
        po.append(
            polib.POEntry(
                msgid=text,
                msgstr="",  # TODO: Fetch this from translation memory
                occurrences=occurances,
            )
        )

    # Write response
    response = HttpResponse(str(po), content_type="text/x-gettext-translation")
    response["Content-Disposition"] = (
        "attachment; filename=translation-%d.po" % translation_request.id
    )
    return response


class MissingSegmentsException(Exception):
    def __init__(self, instance, num_missing):
        self.instance = instance
        self.num_missing = num_missing

        super().__init__()


@require_POST
def upload(request, translation_request_id):
    translation_request = get_object_or_404(
        TranslationRequest, id=translation_request_id
    )

    with tempfile.NamedTemporaryFile() as f:
        f.write(request.FILES["file"].read())
        f.flush()
        po = polib.pofile(f.name)

    translations = {message.msgid: message.msgstr for message in po}

    try:
        with transaction.atomic():
            for page in translation_request.pages.filter(is_completed=False):
                instance = page.source_revision.as_page_object()

                segments = extract_segments(instance)

                text_segments = [
                    segment for segment in segments if isinstance(segment, SegmentValue)
                ]
                template_segments = [
                    segment
                    for segment in segments
                    if isinstance(segment, TemplateValue)
                ]

                translated_segments = template_segments.copy()

                missing_segments = 0
                for segment in text_segments:
                    if segment.text in translations:
                        translated_segments.append(
                            SegmentValue(segment.path, translations[segment.text])
                        )
                    else:
                        missing_segments += 1

                if missing_segments:
                    raise MissingSegmentsException(instance, missing_segments)

                try:
                    translation = instance.get_translation(
                        translation_request.target_locale
                    )
                except instance.__class__.DoesNotExist:
                    translation = instance.copy_for_translation(
                        translation_request.target_locale
                    )

                ingest_segments(
                    instance,
                    translation,
                    translation_request.source_locale,
                    translation_request.target_locale,
                    translated_segments,
                )
                translation.slug = slugify(translation.slug)
                revision = translation.save_revision()

                # Update translation request
                page.is_completed = True
                page.completed_revision = revision
                page.save(update_fields=["is_completed", "completed_revision"])

    except MissingSegmentsException as e:
        # TODO: Plural
        messages.error(
            request,
            "Unable to translate %s. %s missing segments."
            % (e.instance.get_admin_display_title(), e.num_missing),
        )

    else:
        # TODO: Plural
        messages.success(
            request,
            "%d pages successfully translated with PO file"
            % translation_request.pages.count(),
        )

    return redirect(
        "wagtail_localize_workflow_management:detail", translation_request_id
    )
