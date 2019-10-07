from collections import defaultdict

from django.conf import settings
from django.shortcuts import get_object_or_404

from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.core.models import Page

from wagtail_localize.models import Region


def translations_list(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific
    regions = list(Region.objects.filter(is_active=True))

    # Get translations by region
    translations_by_region_unsorted = defaultdict(list)
    for translation in page.get_translations(inclusive=True).select_related("locale"):
        translations_by_region_unsorted[translation.locale.region_id].append(
            translation
        )

    # Now make them a list using region default ordering
    translations_by_region = [
        (region, translations_by_region_unsorted[region.id])
        for region in regions
        if region.id in translations_by_region_unsorted
    ]

    return render_modal_workflow(
        request,
        "wagtail_localize_language_switch/translation_list.html",
        None,
        {
            "page": page,
            "multi_region": len(regions) > 1,
            "translations_by_region": translations_by_region,
        },
    )
