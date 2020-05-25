from django import forms

from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from wagtail.core.models import Page

from wagtail_localize.models import (
    get_translatable_models,
    Locale,
    TranslatablePageMixin,
)

from ..models import TranslationRequest


class CreateTranslationRequestForm(forms.Form):
    locales = forms.ModelMultipleChoiceField(
        queryset=Locale.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    include_subtree = forms.BooleanField(required=False)

    def __init__(self, page, *args, **kwargs):
        super().__init__(*args, **kwargs)

        page_descendant_count = (
            page.get_descendants().type(tuple(get_translatable_models())).count()
        )
        if page_descendant_count > 0:
            self.fields[
                "include_subtree"
            ].help_text = "This will add {} additional pages to the request".format(
                page_descendant_count
            )
        else:
            self.fields["include_subtree"].widget = forms.HiddenInput()

        self.fields["locales"].queryset = Locale.objects.filter(is_active=True).exclude(
            id=page.locale_id
        )


def create_translation_request(request, page_id):
    page = get_object_or_404(Page, id=page_id).specific

    if not isinstance(page, TranslatablePageMixin):
        raise Http404

    if request.method == "POST":
        form = CreateTranslationRequestForm(page, request.POST)

        if form.is_valid():
            with transaction.atomic():
                source_locale = page.locale

                for target_locale in form.cleaned_data["locales"]:
                    instances = []

                    # Add the requested page
                    instances.append(page.specific)

                    # Add the sub tree
                    if form.cleaned_data["include_subtree"]:
                        def _walk(current_page):
                            for child_page in current_page.get_children():
                                if not issubclass(
                                    child_page.specific_class, TranslatablePageMixin
                                ):
                                    continue

                                instances.append(child_page.specific)

                                if child_page.numchild:
                                    _walk(child_page)

                        _walk(page)

                TranslationRequest.from_instances(instances, source_locale, target_locale, user=request.user)

                messages.success(
                    request, "The translation request was submitted successfully"
                )
                return redirect("wagtailadmin_explore", page.get_parent().id)
    else:
        form = CreateTranslationRequestForm(page)

    return render(
        request,
        "wagtail_localize_workflow/create_translation_request.html",
        {"page": page, "form": form},
    )
