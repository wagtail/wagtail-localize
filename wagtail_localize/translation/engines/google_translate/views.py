from collections import defaultdict

from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify

from wagtail_localize.admin.workflow.models import TranslationRequest
from wagtail_localize.translation.segments import SegmentValue, TemplateValue
from wagtail_localize.translation.segments.extract import extract_segments
from wagtail_localize.translation.segments.ingest import ingest_segments

from wagtail_localize.translation.engines.pofile.views import (
    MessageExtractor,
    MessageIngestor,
    MissingSegmentsException,
)

# TODO: Switch to official Google API client
import googletrans


def language_code(code):
    if code in ["zh-hans", "zh-cn"]:
        return "zh-cn"

    if code in ["zh-hant", "zh-tw"]:
        return "zh-tw"

    return code.split("-")[0]


@require_POST
def translate(request, translation_request_id):
    translation_request = get_object_or_404(
        TranslationRequest, id=translation_request_id
    )

    message_extractor = MessageExtractor(translation_request.source_locale)
    for page in translation_request.pages.filter(is_completed=False):
        instance = page.source_revision.as_page_object()
        message_extractor.extract_messages(instance)

    translator = googletrans.Translator()
    google_translations = translator.translate(
        list(message_extractor.messages.keys()),
        src=language_code(translation_request.source_locale.language.code),
        dest=language_code(translation_request.target_locale.language.code),
    )

    translations = {
        translation.origin: translation.text for translation in google_translations
    }

    publish = request.POST.get("publish", "") == "on"

    try:
        with transaction.atomic():
            message_ingestor = MessageIngestor(
                translation_request.source_locale,
                translation_request.target_locale,
                translations,
            )

            for page in translation_request.pages.filter(is_completed=False):
                instance = page.source_revision.as_page_object()
                translation = message_ingestor.ingest_messages(instance)
                revision = translation.get_latest_revision()

                if publish:
                    revision.publish()

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

    # TODO: Plural
    messages.success(
        request,
        "%d pages successfully translated with Google Translate"
        % translation_request.pages.count(),
    )

    return redirect(
        "wagtail_localize_workflow_management:detail", translation_request_id
    )
