from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Sum, Value, When

from .models import Segment, SegmentTranslation, HTMLTemplate, HTMLTemplateSegment, SegmentPageLocation, HTMLTemplatePageLocation


def get_translation_progress(page_revision_id, locale):
    """
    For the specified page revision, get the current
    translation progress into the specified locale.

    Returns two integers:
     - The total number of segments in the revision to translate
     - The number of segments that have been translated into the locale
    """
    # Get QuerySet of Segments that need to be translated
    required_segments = Segment.objects.filter(
        id__in=SegmentPageLocation.objects.filter(page_revision_id=page_revision_id).values_list('segment_id')
    )

    required_segments |= Segment.objects.filter(
        id__in=HTMLTemplateSegment.objects.filter(
            html_template__id__in=HTMLTemplatePageLocation.objects.filter(page_revision_id=page_revision_id).values_list('html_template_id')
        ).values_list('segment_id')
    )

    # Annotate each Segment with a flag that indicates whether the segment is translated
    # into the specified locale
    required_segments = required_segments.annotate(
        is_translated=Exists(
            SegmentTranslation.objects.filter(
                translation_of_id=OuterRef('pk'),
                locale=locale,
            )
        )
    )

    # Count the total number of segments and the number of translated segments
    aggs = required_segments.annotate(
        is_translated_i=Case(
            When(is_translated=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).aggregate(
        total_segments=Count('pk'),
        translated_segments=Sum('is_translated_i'),
    )

    return aggs['total_segments'], aggs['translated_segments']
