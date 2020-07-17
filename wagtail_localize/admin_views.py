from django.shortcuts import get_object_or_404

from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.core.models import Page


def translations_list_modal(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    return render_modal_workflow(
        request,
        "wagtail_localize/admin/translations_list_modal.html",
        None,
        {
            "page": page,
            "translations": page.get_translations(inclusive=True).select_related(
                "locale"
            ),
        },
    )
