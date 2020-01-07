from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Sum,
    Value,
    When,
)

from wagtail_localize.translation.segments import TemplateValue, RelatedObjectValue
from wagtail_localize.translation.segments.extract import extract_segments

from .models import (
    Segment,
    SegmentTranslation,
    SegmentLocation,
    TemplateLocation,
    RelatedObjectLocation,
    TranslatableRevision,
)


def get_translation_progress(revision_id, language):
    """
    For the specified page revision, get the current
    translation progress into the specified language.

    Returns two integers:
     - The total number of segments in the revision to translate
     - The number of segments that have been translated into the language
    """
    # Get QuerySet of Segments that need to be translated
    required_segments = SegmentLocation.objects.filter(revision_id=revision_id)

    # Annotate each Segment with a flag that indicates whether the segment is translated
    # into the specified language
    required_segments = required_segments.annotate(
        is_translated=Exists(
            SegmentTranslation.objects.filter(
                translation_of_id=OuterRef("segment_id"),
                context_id=OuterRef("context_id"),
                language=language,
            )
        )
    )

    # Count the total number of segments and the number of translated segments
    aggs = required_segments.annotate(
        is_translated_i=Case(
            When(is_translated=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).aggregate(total_segments=Count("pk"), translated_segments=Sum("is_translated_i"))

    return aggs["total_segments"], aggs["translated_segments"]


def insert_segments(revision, language, segments):
    """
    Inserts the list of untranslated segments into translation memory
    """
    for segment in segments:
        if isinstance(segment, TemplateValue):
            TemplateLocation.from_template_value(revision, segment)
        elif isinstance(segment, RelatedObjectValue):
            RelatedObjectLocation.from_related_object_value(revision, segment)
        else:
            SegmentLocation.from_segment_value(revision, language, segment)
