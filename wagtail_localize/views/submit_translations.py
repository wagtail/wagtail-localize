from django import forms
from django.contrib import messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import Locale, Page, TranslatableMixin
from wagtail.snippets.views.snippets import get_snippet_model_from_url_params

from wagtail_localize.compat import get_snippet_edit_url_from_args
from wagtail_localize.components import TranslationComponentManager
from wagtail_localize.operations import translate_object, translate_page_subtree
from wagtail_localize.tasks import background


class SubmitTranslationForm(forms.Form):
    # Note: We don't actually use select_all in Python., is is just the
    # easiest way to add the widget to the form. It's controlled in JS.
    select_all = forms.BooleanField(label=gettext_lazy("Select all"), required=False)
    locales = forms.ModelMultipleChoiceField(
        label=gettext_lazy("Locales"),
        queryset=Locale.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    include_subtree = forms.BooleanField(
        required=False, help_text=gettext_lazy("All child pages will be created.")
    )

    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)

        hide_include_subtree = True

        if isinstance(instance, Page):
            descendant_count = instance.get_descendants().count()

            if descendant_count > 0:
                hide_include_subtree = False
                self.fields["include_subtree"].label = ngettext(
                    "Include subtree ({} page)",
                    "Include subtree ({} pages)",
                    descendant_count,
                ).format(descendant_count)

        if hide_include_subtree:
            self.fields["include_subtree"].widget = forms.HiddenInput()

        existing_translations = instance.get_translations(inclusive=True)

        # Don't count page aliases as existing translations. We can convert aliases into properly translated pages
        if isinstance(instance, Page):
            existing_translations = existing_translations.exclude(
                alias_of__isnull=False
            )

        self.fields["locales"].queryset = Locale.objects.exclude(
            id__in=existing_translations.values_list("locale_id", flat=True)
        )

        # Using len() instead of count() here as we're going to evaluate this queryset
        # anyway and it gets cached so it'll only have one query in the end.
        if len(self.fields["locales"].queryset) < 2:
            self.fields["select_all"].widget = forms.HiddenInput()


class SubmitTranslationView(SingleObjectMixin, TemplateView):
    template_name = "wagtail_localize/admin/submit_translation.html"
    title = gettext_lazy("Translate")

    def get_title(self):
        return self.title

    def get_subtitle(self):
        return str(self.object)

    def get_form(self):
        if self.request.method == "POST":
            return SubmitTranslationForm(self.object, self.request.POST)
        else:
            initial = None
            if self.request.GET.get("select_locale", None):
                select_locale = Locale.objects.filter(
                    language_code=self.request.GET["select_locale"]
                ).first()
                if select_locale:
                    initial = {"locales": [select_locale]}

            return SubmitTranslationForm(self.object, initial=initial)

    def get_success_url(self):
        return get_valid_next_url_from_request(self.request)

    def get_default_success_url(self, translated_object=None):
        pass

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form": self.get_form(),
                "next_url": self.get_success_url(),
                "back_url": self.get_success_url() or self.get_default_success_url(),
                "components": self.components,
            }
        )
        return context

    def post(self, request, **kwargs):
        form = self.get_form()

        if form.is_valid() and self.components.is_valid():
            return self.form_valid(form)

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    @transaction.atomic
    def form_valid(self, form):
        translate_object(
            self.object,
            form.cleaned_data["locales"],
            self.components,
            self.request.user,
        )

        # Now add the sub tree (if the obj is a page)
        if isinstance(self.object, Page) and form.cleaned_data["include_subtree"]:
            # Translating a subtree may be a heavy task, so enqueue it into the background
            # (note, we always want to translate the root here so that we have something to redirect to)
            background.enqueue(
                translate_page_subtree,
                [
                    self.object.id,
                    form.cleaned_data["locales"],
                    self.components,
                    self.request.user,
                ],
                {},
            )

        single_translated_object = None
        if len(form.cleaned_data["locales"]) == 1:
            locales = form.cleaned_data["locales"][0].get_display_name()
            single_translated_object = self.object.get_translation(
                form.cleaned_data["locales"][0]
            )

        else:
            # Note: always plural
            locales = _("{} locales").format(len(form.cleaned_data["locales"]))

        # TODO: Button that links to page in translations report when we have it
        messages.success(self.request, self.get_success_message(locales))

        return redirect(
            self.get_success_url()
            or self.get_default_success_url(single_translated_object)
        )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perms(["wagtail_localize.submit_translation"]):
            raise PermissionDenied

        self.object = self.get_object()
        self.components = TranslationComponentManager.from_request(
            self.request, source_object_instance=self.object
        )
        return super().dispatch(request, *args, **kwargs)


class SubmitPageTranslationView(SubmitTranslationView):
    title = gettext_lazy("Translate page")

    def get_subtitle(self):
        return self.object.get_admin_display_title()

    def get_object(self):
        page = get_object_or_404(Page, id=self.kwargs["page_id"]).specific

        # Can't translate the root page
        if page.is_root():
            raise Http404

        return page

    def get_default_success_url(self, translated_page=None):
        if translated_page:
            # If the editor chose a single locale to translate to, redirect to
            # the newly translated page's edit view.
            return reverse("wagtailadmin_pages:edit", args=[translated_page.id])

        return reverse("wagtailadmin_explore", args=[self.get_object().get_parent().id])

    def get_success_message(self, locales):
        return _(
            "The page '{page_title}' was successfully submitted for translation into {locales}"
        ).format(page_title=self.object.get_admin_display_title(), locales=locales)


class SubmitSnippetTranslationView(SubmitTranslationView):
    def get_title(self):
        return _("Translate {model_name}").format(
            model_name=self.object._meta.verbose_name
        )

    def get_object(self):
        model = get_snippet_model_from_url_params(
            self.kwargs["app_label"], self.kwargs["model_name"]
        )

        if not issubclass(model, TranslatableMixin):
            raise Http404

        return get_object_or_404(model, pk=unquote(self.kwargs["pk"]))

    def get_default_success_url(self, translated_snippet=None):
        if translated_snippet:
            # If the editor chose a single locale to translate to, redirect to
            # the newly translated snippet's edit view.
            return get_snippet_edit_url_from_args(
                self.kwargs["app_label"],
                self.kwargs["model_name"],
                translated_snippet.pk,
            )

        return get_snippet_edit_url_from_args(
            self.kwargs["app_label"],
            self.kwargs["model_name"],
            self.kwargs["pk"],
        )

    def get_success_message(self, locales):
        return _(
            "The {model_name} '{object}' was successfully submitted for translation into {locales}"
        ).format(
            model_name=self.object._meta.verbose_name,
            object=str(self.object),
            locales=locales,
        )
