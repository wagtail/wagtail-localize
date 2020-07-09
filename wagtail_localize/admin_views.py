from django.apps import apps
from django.http import Http404
from django.shortcuts import get_object_or_404

from wagtail.admin.modal_workflow import render_modal_workflow
from wagtail.core.models import Page

from wagtail_localize.models import TranslatablePageMixin


def translations_list_modal(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    if not isinstance(page, TranslatablePageMixin):
        raise Http404("Page is not translatable")

    translations = [{'instance': instance} for instance in page.get_translations(inclusive=True).select_related("locale")]

    # Attach Translation objects to translated instances if the translation app is installed
    # TODO: Display translation objects that don't have instances yet?
    has_translation_objects = False
    if apps.is_installed("wagtail_localize.translation"):
        from wagtail_localize.translation.models import TranslatableObject

        # Fetch translatable object for page
        try:
            translatable_object = TranslatableObject.objects.get_for_instance(page)
        except TranslatableObject.DoesNotExist:
            pass

        else:
            # Fetch translation object for each locale
            for translation in translations:
                translation['translation'] = translatable_object.translations.filter(target_locale=translation['instance'].locale).first()
                has_translation_objects = True

    return render_modal_workflow(
        request,
        "wagtail_localize/admin/translations_list_modal.html",
        None,
        {
            "page": page,
            "has_translation_objects": has_translation_objects,
            "translations": translations,
        },
    )
