from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from wagtail.admin import messages
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import Page

from wagtail_localize.models import Translation


def convert_to_alias(request, page_id):
    page = get_object_or_404(Page, id=page_id, alias_of_id__isnull=True)
    if not page.permissions_for_user(request.user).can_edit():
        raise PermissionDenied

    try:
        source_locale_id = Translation.objects.filter(
            source__object_id=page.translation_key,
            target_locale_id=page.locale_id,
        ).values_list("source__locale_id", flat=True)[0]
    except (Translation.DoesNotExist, IndexError):
        raise Http404

    try:
        source_page_id = Page.objects.filter(
            translation_key=page.translation_key, locale_id=source_locale_id
        ).values_list("pk", flat=True)[0]
    except (Page.DoesNotExist, IndexError):
        raise Http404

    with transaction.atomic():
        next_url = get_valid_next_url_from_request(request)

        if request.method == "POST":
            page.alias_of_id = source_page_id
            page.save(update_fields=["alias_of_id"], clean=False)

            # TODO: log entry

            messages.success(
                request,
                _("Page '{}' has been converted into an alias.").format(
                    page.get_admin_display_title()
                ),
            )

            if next_url:
                return redirect(next_url)
            return redirect("wagtailadmin_pages:edit", page.id)

    return TemplateResponse(
        request,
        "wagtail_localize/admin/confirm_convert_to_alias.html",
        {
            "page": page,
            "next": next_url,
        },
    )
