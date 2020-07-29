from django import forms

from django.contrib import messages
from django.contrib.admin.utils import quote, unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.translation import gettext as _
from wagtail.admin.views.pages import get_valid_next_url_from_request
from wagtail.core.models import Page, Locale, TranslatableMixin
from wagtail.snippets.views.snippets import get_snippet_model_from_url_params

from wagtail_localize.models import Translation, TranslationSource


class SubmitTranslationForm(forms.Form):
    locales = forms.ModelMultipleChoiceField(
        queryset=Locale.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    include_subtree = forms.BooleanField(required=False)

    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(instance, Page):
            page_descendant_count = instance.get_descendants().count()
        else:
            page_descendant_count = 0

        if page_descendant_count > 0:
            self.fields[
                "include_subtree"
            ].help_text = "This will add {} additional pages to the request".format(
                page_descendant_count
            )
        else:
            self.fields["include_subtree"].widget = forms.HiddenInput()

        self.fields["locales"].queryset = Locale.objects.exclude(
            id=instance.locale_id
        )


class TranslationCreator:
    """
    A class that provides a create_translations method.

    Call create_translations for each object you want to translate and this will submit
    that object and any dependencies as well.

    This class will track the objects that have already submitted so an object doesn't
    get submitted twice.
    """
    def __init__(self, user, target_locales):
        self.user = user
        self.target_locales = target_locales
        self.seen_objects = set()

    def create_translations(self, instance, include_related_objects=True):
        if isinstance(instance, Page):
            instance = instance.specific

        if instance.translation_key in self.seen_objects:
            return
        self.seen_objects.add(instance.translation_key)

        source, created = TranslationSource.get_or_create_from_instance(instance)

        # Add related objects
        # Must be before translation records or those translation records won't be able to create
        # the objects because the dependencies haven't been created
        if include_related_objects:
            for related_object_segment in source.relatedobjectsegment_set.all():
                related_instance = related_object_segment.object.get_instance(instance.locale)

                # Limit to one level of related objects, since this could potentially pull in a lot of stuff
                self.create_translations(related_instance, include_related_objects=False)

        # Set up translation records
        for target_locale in self.target_locales:
            # Create translation if it doesn't exist yet
            translation, created = Translation.objects.get_or_create(
                source=source,
                target_locale=target_locale,
            )

            if created:
                translation.save_target(user=self.user)


def submit_page_translation(request, page_id):
    if not request.user.has_perms(['wagtail_localize.submit_translation']):
        raise PermissionDenied

    page = get_object_or_404(Page, id=page_id).specific
    next_url = get_valid_next_url_from_request(request)

    if request.method == "POST":
        form = SubmitTranslationForm(page, request.POST)

        if form.is_valid():
            with transaction.atomic():
                translator = TranslationCreator(request.user, form.cleaned_data["locales"])
                translator.create_translations(page)

                # Now add the sub tree
                if form.cleaned_data["include_subtree"]:
                    def _walk(current_page):
                        for child_page in current_page.get_children():
                            translator.create_translations(child_page)

                            if child_page.numchild:
                                _walk(child_page)

                    _walk(page)

                if len(form.cleaned_data["locales"]) == 1:
                    locales = form.cleaned_data["locales"][0].get_display_name()

                else:
                    # Note: always plural
                    locales = _('{} locales').format(len(form.cleaned_data["locales"]))

                # TODO: Button that links to page in translations report when we have it
                messages.success(
                    request, _("The page '{}' was successfully submitted for translation into {}").format(page.title, locales)
                )

                if next_url:
                    return redirect(next_url)
                else:
                    return redirect("wagtailadmin_explore", page.get_parent().id)
    else:
        form = SubmitTranslationForm(page)

    return render(
        request,
        "wagtail_localize/admin/submit_page_translation.html",
        {"page": page, "form": form, "next_url": next_url},
    )


def submit_snippet_translation(request, app_label, model_name, pk):
    if not request.user.has_perms(['wagtail_localize.submit_translation']):
        raise PermissionDenied

    model = get_snippet_model_from_url_params(app_label, model_name)

    if not issubclass(model, TranslatableMixin):
        raise Http404

    instance = get_object_or_404(model, pk=unquote(pk))
    next_url = get_valid_next_url_from_request(request)

    if request.method == "POST":
        form = SubmitTranslationForm(instance, request.POST)

        if form.is_valid():
            with transaction.atomic():
                translator = TranslationCreator(request.user, form.cleaned_data["locales"])
                translator.create_translations(instance)

                if len(form.cleaned_data["locales"]) == 1:
                    locales = form.cleaned_data["locales"][0].get_display_name()
                else:
                    # Note: always plural
                    locales = _('{} locales').format(len(form.cleaned_data["locales"]))

                # TODO: Button that links to snippet in translations report when we have it
                messages.success(
                    request, _("The {} '{}' was successfully submitted for translation into {}").format(model._meta.verbose_name.title(), (str(instance)), locales)
                )

                if next_url:
                    return redirect(next_url)
                else:
                    return redirect("wagtailsnippets:edit", app_label, model_name, quote(pk))
    else:
        form = SubmitTranslationForm(instance)

    return render(
        request,
        "wagtail_localize/admin/submit_snippet_translation.html",
        {
            "app_label": app_label,
            "model_name": model_name,
            "model_verbose_name": model._meta.verbose_name.title(),
            "instance": instance,
            "form": form,
            "next_url": next_url,
        }
    )
