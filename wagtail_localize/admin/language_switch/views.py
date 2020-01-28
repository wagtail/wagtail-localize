from collections import defaultdict

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404

from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.core.models import Page

from wagtail_localize.models import TranslatablePageMixin


def translations_list(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    if not isinstance(page, TranslatablePageMixin):
        raise Http404("Page is not translatable")

    return render_modal_workflow(
        request,
        "wagtail_localize_language_switch/translation_list.html",
        None,
        {
            "page": page,
            "translations": page.get_translations(inclusive=True).select_related(
                "locale"
            ),
        },
    )
