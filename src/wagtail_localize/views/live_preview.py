from __future__ import annotations

import json

from collections.abc import Mapping

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from wagtail.models import Page
from wagtail.utils.decorators import xframe_options_sameorigin_override

from wagtail_localize.models import OverridableSegment, StringSegment, Translation
from wagtail_localize.segments.ingest import ingest_segments
from wagtail_localize.segments.types import (
    OverridableSegmentValue,
    StringSegmentValue,
)
from wagtail_localize.strings import StringValue
from wagtail_localize.views.edit_translation import user_can_edit_instance


def _session_key(translation_id: int) -> str:
    return f"wagtail-localize-live-preview-{translation_id}"


def _invalid_response(request, translation_id: int) -> JsonResponse:
    return JsonResponse(
        {
            "is_valid": False,
            "is_available": bool(request.session.get(_session_key(translation_id))),
        }
    )


def _parse_payload(payload):
    if not isinstance(payload, Mapping):
        raise ValueError

    string_values = payload.get("stringTranslations", {})
    override_values = payload.get("segmentOverrides", {})
    if not isinstance(string_values, dict) or not isinstance(override_values, dict):
        raise ValueError
    return string_values, override_values


def _get_preview_values(translation, payload):
    string_values, override_values = _parse_payload(payload)
    source = translation.source
    valid_string_ids = {
        str(pk)
        for pk in StringSegment.objects.filter(source=source).values_list("id", flat=True)
    }
    valid_override_ids = {
        str(pk)
        for pk in OverridableSegment.objects.filter(source=source).values_list(
            "id", flat=True
        )
    }

    if set(string_values) - valid_string_ids or set(override_values) - valid_override_ids:
        raise ValueError
    if any(not isinstance(value, str) for value in string_values.values()):
        raise ValueError
    return string_values, override_values


def _replace_ephemeral_values(translation, string_values, override_values):
    source = translation.source
    instance = source.get_ephemeral_translated_instance(
        translation.target_locale, fallback=True
    )
    segments = source._get_segments_for_translation(
        translation.target_locale, fallback=True
    )

    strings_by_key = {
        (segment.context.path, segment.order): string_values[str(segment.id)]
        for segment in StringSegment.objects.filter(source=source).select_related("context")
        if str(segment.id) in string_values
    }
    override_segments = list(
        OverridableSegment.objects.filter(source=source).select_related("context")
    )
    overrides_by_key = {
        (segment.context.path, segment.order): override_values[str(segment.id)]
        for segment in override_segments
        if str(segment.id) in override_values
    }

    replaced = []
    represented_override_keys = set()
    for segment in segments:
        key = (segment.path, segment.order)
        if isinstance(segment, StringSegmentValue) and key in strings_by_key:
            replaced.append(
                StringSegmentValue(
                    segment.path,
                    StringValue.from_plaintext(strings_by_key[key]),
                    attrs=segment.attrs,
                    order=segment.order,
                )
            )
        elif isinstance(segment, OverridableSegmentValue) and key in overrides_by_key:
            represented_override_keys.add(key)
            replaced.append(
                OverridableSegmentValue(
                    segment.path, overrides_by_key[key], order=segment.order
                )
            )
        else:
            replaced.append(segment)

    for segment in override_segments:
        key = (segment.context.path, segment.order)
        if str(segment.id) in override_values and key not in represented_override_keys:
            replaced.append(
                OverridableSegmentValue(
                    segment.context.path, override_values[str(segment.id)], order=segment.order
                )
            )

    ingest_segments(
        source.as_instance(),
        instance,
        source.locale,
        translation.target_locale,
        replaced,
    )
    return instance


@xframe_options_sameorigin_override
@require_http_methods(["DELETE", "GET", "POST"])
def live_preview(request, translation_id, mode=None):
    translation = get_object_or_404(Translation, id=translation_id)
    target = translation.get_target_instance()
    if not isinstance(target, Page):
        raise Http404 from None
    if not user_can_edit_instance(request.user, target):
        raise PermissionDenied

    if request.method == "DELETE":
        request.session.pop(_session_key(translation_id), None)
        request.session.modified = True
        return HttpResponse(status=204)

    if request.method == "POST":
        try:
            payload = json.loads(request.POST.get("payload", ""))
            string_values, override_values = _get_preview_values(translation, payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return _invalid_response(request, translation_id)

        request.session[_session_key(translation_id)] = json.dumps(
            {
                "stringTranslations": string_values,
                "segmentOverrides": override_values,
            }
        )
        request.session.modified = True
        return JsonResponse({"is_valid": True, "is_available": True})

    mode = request.GET.get("mode", mode) or target.default_preview_mode
    if mode not in dict(target.preview_modes):
        raise Http404

    try:
        payload = json.loads(request.session[_session_key(translation_id)])
        string_values, override_values = _get_preview_values(translation, payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise Http404 from None

    ephemeral = _replace_ephemeral_values(translation, string_values, override_values)
    return ephemeral.make_preview_request(
        request,
        mode,
        {"in_preview_panel": request.GET.get("in_preview_panel") == "true", "is_editing": True},
    )
