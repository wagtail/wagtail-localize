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
    pk,
    Segment,
    SegmentTranslation,
    SegmentLocation,
    TemplateLocation,
    RelatedObjectLocation,
    TranslatableRevision,
)


class TranslationProgress:
    def __init__(self, total_segments, translated_segments, total_related_objects, translated_related_objects):
        self.total_segments = total_segments
        self.translated_segments = translated_segments
        self.total_related_objects = total_related_objects
        self.translated_related_objects = translated_related_objects

    def is_ready(self):
        return self.total_segments == self.translated_segments and self.total_related_objects == self.translated_related_objects


def get_translation_progress(revision, locale):
    """
    For the specified page revision, get the current
    translation progress into the specified locale.

    The revision/locale arguments can either be objects or IDs
    """
    # Get QuerySet of Segments that need to be translated
    required_segments = SegmentLocation.objects.filter(revision_id=pk(revision))

    # Annotate each Segment with a flag that indicates whether the segment is translated
    # into the specified locale
    required_segments = required_segments.annotate(
        is_translated=Exists(
            SegmentTranslation.objects.filter(
                translation_of_id=OuterRef("segment_id"),
                context_id=OuterRef("context_id"),
                locale_id=pk(locale),
            )
        )
    )

    # Count the total number of segments and the number of translated segments
    segment_aggs = required_segments.annotate(
        is_translated_i=Case(
            When(is_translated=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).aggregate(total_segments=Count("pk"), translated_segments=Sum("is_translated_i"))

    # Work out how many required related objects have been translated
    required_related_objects = RelatedObjectLocation.objects.filter(revision_id=pk(revision))
    total_related_objects = 0
    translated_related_objects = 0
    for related_object in required_related_objects:
        total_related_objects += 1

        if related_object.has_translation(locale):
            translated_related_objects += 1

    return TranslationProgress(
        segment_aggs["total_segments"],
        segment_aggs["translated_segments"],
        total_related_objects,
        translated_related_objects,
    )


def insert_segments(revision, locale, segments):
    """
    Inserts the list of untranslated segments into translation memory
    """
    for segment in segments:
        if isinstance(segment, TemplateValue):
            TemplateLocation.from_template_value(revision, segment)
        elif isinstance(segment, RelatedObjectValue):
            RelatedObjectLocation.from_related_object_value(revision, segment)
        else:
            SegmentLocation.from_segment_value(revision, locale, segment)
