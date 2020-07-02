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

from wagtail_localize.translation.machine_translators import get_machine_translator
from wagtail_localize.translation.models import Translation, SegmentTranslation, SegmentLocation
from wagtail_localize.translation.segments import SegmentValue


# TODO: Permission checks
@require_GET
def export_file(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    # Get messages
    messages = defaultdict(list)

    segment_locations = (
        SegmentLocation.objects.filter(source=translation.source)
        .select_related("context", "segment")
        .annotate_translation(translation.target_locale)
    )

    for location in segment_locations:
        messages[location.segment.text] = (location.context.path, location.translation)

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


# TODO: Permission checks
@require_POST
def import_file(request, translation_id=None):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    with tempfile.NamedTemporaryFile() as f:
        f.write(request.FILES["file"].read())
        f.flush()
        po = polib.pofile(f.name)

    translations = {message.msgid: message.msgstr for message in po}

    with transaction.atomic():
        for location in translation.source.segmentlocation_set.all().select_related("context", "segment"):
            # TODO: Take context into account here
            translated_text = translations[location.segment.text]

            SegmentTranslation.objects.get_or_create(
                translation_of_id=location.segment_id,
                locale=translation.target_locale,
                context_id=location.context_id,
                defaults={
                    'text': translated_text,
                }
            )

        translation.update(user=request.user)

    # TODO: Plural
    messages.success(
        request,
        "successfully translated"
    )

    return redirect(
        "wagtail_localize_translation_management:detail", translation_id
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

        translation.update(user=request.user)

    messages.success(
        request,
        "Saved translations"
    )

    return redirect(
        "wagtail_localize_translation_management:detail", translation_id
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

    with transaction.atomic():
        for source_text, (segment_id, context_id) in segments.items():
            # TODO: Take context into account here
            translated_text = translations[source_text]

            SegmentTranslation.objects.get_or_create(
                translation_of_id=segment_id,
                locale=translation.target_locale,
                context_id=context_id,
                defaults={
                    'text': translated_text,
                }
            )

        translation.update(user=request.user)

    # TODO: Plural
    messages.success(
        request,
        "successfully translated"
    )

    return redirect(
        "wagtail_localize_translation_management:detail", translation_id
    )
