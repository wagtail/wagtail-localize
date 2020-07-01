import json
import tempfile
from collections import defaultdict

import polib
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from wagtail.core.models import Page

from wagtail_localize.translation.machine_translators import get_machine_translator
from wagtail_localize.translation.models import Translation, TranslationSource, SegmentTranslation
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

    def extract_messages(self, source):
        if source.object_id in self.seen_objects:
            return
        self.seen_objects.add(source.object_id)

        for segment in source.get_segments():
            if isinstance(segment, SegmentValue):
                self.messages[segment.html].append(
                    (self.get_path(instance), segment.path)
                )
            #elif isinstance(segment, RelatedObjectValue):
            #    self.extract_messages(segment.get_instance(self.locale))


# TODO: Permission checks
@require_GET
def export_file(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    # Get messages
    messages = defaultdict(list)
    for segment in translation.source.get_segments(with_translation=translation.target_locale, raise_if_missing_translation=False):
        if isinstance(segment, SegmentValue):
            messages[segment.html_with_ids] = (segment.path, segment.translation.html_with_ids if segment.translation else None)

    # TODO: We need to make sure we handle the case where two strings have the same source and context.
    # For example, if I have a rich text field with two links that have the same text but go to different places
    # We only want to include this once for translation

    # Build a PO file
    po = polib.POFile()
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
        "X-WagtailLocalize-TranslationID": str(translation.uuid),
    }

    for text, (context, translated_text) in messages.items():
        po.append(
            polib.POEntry(
                msgid=text,
                msgctxt=context,
                msgstr=translated_text or "",
            )
        )

    # Write response
    response = HttpResponse(str(po), content_type="text/x-gettext-translation")
    response["Content-Disposition"] = (
        "attachment; filename=translation-%d.po" % translation.id
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

        source = TranslationSource.objects.get_for_instance(instance).order_by('-created_at').first()
        if source is None:
            raise Exception("Source was None?")

        segments = source.get_segments()

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
            if segment.html in self.translations:
                translated_segments.append(
                    SegmentValue.from_html(
                        segment.path,
                        self.translations[segment.html],
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


# TODO: Permission checks
@require_POST
def import_file(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    with tempfile.NamedTemporaryFile() as f:
        f.write(request.FILES["file"].read())
        f.flush()
        po = polib.pofile(f.name)

    translations = {message.msgid: message.msgstr for message in po}

    try:
        with transaction.atomic():
            message_ingestor = MessageIngestor(
                translation.source.locale,
                translation.target_locale,
                translations,
            )

            for page in translation.pages.filter(is_completed=False):
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
            % translation.pages.count(),
        )

    return redirect(
        "wagtail_localize_workflow_management:detail", translation_id
    )


# TODO: Permission checks
@require_POST
def translation_form(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    with transaction.atomic():
        for segment in translation.source.segmentlocation_set.all():
            value = request.POST.get(f"segment-{segment.id}", "")

            if value:
                SegmentTranslation.objects.update_or_create(
                    translation_of_id=segment.segment_id,
                    locale_id=translation.target_locale_id,
                    context_id=segment.context_id,
                    defaults={
                        'text': value
                    }
                )
            else:
                SegmentTranslation.objects.filter(
                    translation_of_id=segment.segment_id,
                    locale_id=translation.target_locale_id,
                    context_id=segment.context_id,
                ).delete()

    messages.success(
        request,
        "Saved translations"
    )


    return redirect(
        "wagtail_localize_workflow_management:detail", translation_id
    )


# TODO: Permission checks
@require_POST
def machine_translate(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    translator = get_machine_translator()
    if translator is None:
        return Http404

    # Get segments
    segments = defaultdict(list)
    for location in translation.source.segmentlocation_set.all().select_related("context", "segment"):
        segment = SegmentValue.from_html(
            location.context.path, location.segment.text
        ).with_order(location.order)
        if location.html_attrs:
            segment.replace_html_attrs(json.loads(location.html_attrs))

        # Don't translate if there already is a translation
        if SegmentTranslation.objects.filter(
            translation_of_id=location.segment_id,
            locale=translation.target_locale,
            context_id=location.context_id,
        ).exists():
            continue

        segments[segment.html_with_ids] = (location.segment_id, location.context_id)

    # TODO: We need to make sure we handle the case where two strings have the same source and context.
    # For example, if I have a rich text field with two links that have the same text but go to different places
    # We only want to include this once for translation

    translations = translator.translate(translation.source.locale, translation.target_locale, segments.keys())

    try:
        with transaction.atomic():
            for source_text, (segment_id, context_id) in segments.items():
                translated_text = translations[source_text]

                SegmentTranslation.objects.get_or_create(
                    translation_of_id=segment_id,
                    locale=translation.target_locale,
                    context_id=context_id,
                    defaults={
                        'text': translated_text,
                    }
                )

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
            "successfully translated"
        )

    return redirect(
        "wagtail_localize_workflow_management:detail", translation_id
    )
