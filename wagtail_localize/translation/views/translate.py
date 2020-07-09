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
from wagtail_localize.translation.models import Translation, StringTranslation, StringSegment
from wagtail_localize.translation.segments import StringSegmentValue


# TODO: Permission checks
@require_GET
def export_file(request, translation_id):
    translation = get_object_or_404(
        Translation, id=translation_id
    )

    # Get messages
    messages = defaultdict(list)

    string_segments = (
        StringSegment.objects.filter(source=translation.source)
        .select_related("context", "string")
        .annotate_translation(translation.target_locale)
    )

    for string_segment in string_segments:
        messages[string_segment.string.data] = (string_segment.context.path, string_segment.translation)

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
        for string_segment in translation.source.stringsegment_set.all().select_related("context", "string"):
            # TODO: Take context into account here
            string_translation = translations[string_segment.string.data]

            StringTranslation.objects.get_or_create(
                translation_of_id=string_segment.string_id,
                locale=translation.target_locale,
                context_id=string_segment.context_id,
                defaults={
                    'data': string_translation,
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
        for segment in translation.source.stringsegment_set.all():
            translation = request.POST.get(f"segment-{segment.id}", "")

            if translation:
                StringTranslation.objects.update_or_create(
                    translation_of_id=segment.string_id,
                    locale_id=translation.target_locale_id,
                    context_id=segment.context_id,
                    defaults={
                        'data': translation
                    }
                )
            else:
                StringTranslation.objects.filter(
                    translation_of_id=segment.string_id,
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
    for string_segment in translation.source.stringsegment_set.all().select_related("context", "string"):
        segment = StringSegmentValue.from_html(
            string_segment.context.path, string_segment.string.data
        ).with_order(string_segment.order)
        if string_segment.attrs:
            segment.attrs = json.loads(string_segment.attrs)

        # Don't translate if there already is a translation
        if StringTranslation.objects.filter(
            translation_of_id=string_segment.string_id,
            locale=translation.target_locale,
            context_id=string_segment.context_id,
        ).exists():
            continue

        segments[segment.string] = (string_segment.string_id, string_segment.context_id)

    # TODO: We need to make sure we handle the case where two strings have the same source and context.
    # For example, if I have a rich text field with two links that have the same text but go to different places
    # We only want to include this once for translation

    translations = translator.translate(translation.source.locale, translation.target_locale, segments.keys())

    with transaction.atomic():
        for string, (string_id, context_id) in segments.items():
            # TODO: Take context into account here
            print(translations)
            print(string)
            string_translation = translations[string]

            StringTranslation.objects.get_or_create(
                translation_of_id=string_id,
                locale=translation.target_locale,
                context_id=context_id,
                defaults={
                    'data': string_translation.data,
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
