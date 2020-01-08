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
from wagtail.core.models import Page

from wagtail_localize.admin.workflow.models import TranslationRequest
from wagtail_localize.translation.segments import (
    SegmentValue,
    TemplateValue,
    RelatedObjectValue,
)
from wagtail_localize.translation.segments.extract import extract_segments
from wagtail_localize.translation.segments.ingest import ingest_segments


class MessageExtractor:
    def __init__(self, locale):
        self.locale = locale
        self.seen_objects = set()
        self.messages = defaultdict(list)

    def get_path(self, instance):
        if isinstance(instance, Page):
            return "pages" + instance.url_path
        else:
            base_model = instance.get_translation_model()
            return f"{slugify(base_model._meta.verbose_name_plural)}/{instance.pk}"

    def extract_messages(self, instance):
        if instance.translation_key in self.seen_objects:
            return
        self.seen_objects.add(instance.translation_key)

        for segment in extract_segments(instance):
            if isinstance(segment, SegmentValue):
                self.messages[segment.text].append(
                    (self.get_path(instance), segment.path)
                )
            elif isinstance(segment, RelatedObjectValue):
                self.extract_messages(segment.get_instance(self.locale))


@require_GET
def download(request, translation_request_id):
    translation_request = get_object_or_404(
        TranslationRequest, id=translation_request_id
    )

    # Extract messages from pages
    message_extractor = MessageExtractor(translation_request.source_locale)
    for page in translation_request.pages.all():
        instance = page.source_revision.as_page_object()
        message_extractor.extract_messages(instance)

    # Build a PO file
    po = polib.POFile()
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
    }

    for text, occurances in message_extractor.messages.items():
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


class MessageIngestor:
    def __init__(self, source_locale, target_locale, translations):
        self.source_locale = source_locale
        self.target_locale = target_locale
        self.translations = translations
        self.seen_objects = set()

    def ingest_messages(self, instance):
        if instance.translation_key in self.seen_objects:
            return
        self.seen_objects.add(instance.translation_key)

        segments = extract_segments(instance)

        # Ingest segments for dependencies first
        for segment in segments:
            if isinstance(segment, RelatedObjectValue):
                self.ingest_messages(segment.get_instance(self.source_locale))

        text_segments = [
            segment for segment in segments if isinstance(segment, SegmentValue)
        ]

        # Initialise translated segments by copying templates and related objects
        translated_segments = [
            segment
            for segment in segments
            if isinstance(segment, (TemplateValue, RelatedObjectValue))
        ]

        missing_segments = 0
        for segment in text_segments:
            if segment.text in self.translations:
                translated_segments.append(
                    SegmentValue(
                        segment.path,
                        self.translations[segment.text],
                        order=segment.order,
                    )
                )
            else:
                missing_segments += 1

        if missing_segments:
            raise MissingSegmentsException(instance, missing_segments)

        translated_segments.sort(key=lambda segment: segment.order)

        try:
            translation = instance.get_translation(self.target_locale)
        except instance.__class__.DoesNotExist:
            translation = instance.copy_for_translation(self.target_locale)

        ingest_segments(
            instance,
            translation,
            self.source_locale,
            self.target_locale,
            translated_segments,
        )

        if isinstance(translation, Page):
            translation.slug = slugify(translation.slug)
            revision = translation.save_revision()
        else:
            translation.save()

        return translation


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
            message_ingestor = MessageIngestor(
                translation_request.source_locale,
                translation_request.target_locale,
                translations,
            )

            for page in translation_request.pages.filter(is_completed=False):
                instance = page.source_revision.as_page_object()
                translation = message_ingestor.ingest_messages(instance)

                # Update translation request
                page.is_completed = True
                page.completed_revision = translation.get_latest_revision()
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
