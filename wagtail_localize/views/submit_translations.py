from django import forms

from django.contrib import messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy as __, ngettext
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import Page, Locale, TranslatableMixin
from wagtail.snippets.views.snippets import get_snippet_model_from_url_params

from wagtail_localize.models import Translation, TranslationSource


class SubmitTranslationForm(forms.Form):
    # Note: We don't actually use select_all in Python., is is just the
    # easiest way to add the widget to the form. It's controlled in JS.
    select_all = forms.BooleanField(label=__("Select all"), required=False)
    locales = forms.ModelMultipleChoiceField(
        label=__("Locales"), queryset=Locale.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    include_subtree = forms.BooleanField(required=False, help_text=__("All child pages will be created."))

    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)

        hide_include_subtree = True

        if isinstance(instance, Page):
            descendant_count = instance.get_descendants().count()

            if descendant_count > 0:
                hide_include_subtree = False
                self.fields["include_subtree"].label = ngettext("Include subtree ({} page)", "Include subtree ({} pages)", descendant_count).format(descendant_count)

        if hide_include_subtree:
            self.fields["include_subtree"].widget = forms.HiddenInput()

        existing_translations = instance.get_translations(inclusive=True)

        # Don't count page aliases as existing translations. We can convert aliases into properly translated pages
        if isinstance(instance, Page):
            existing_translations = existing_translations.exclude(alias_of__isnull=False)

        self.fields["locales"].queryset = Locale.objects.exclude(
            id__in=existing_translations.values_list('locale_id', flat=True)
        )

        # Using len() instead of count() here as we're going to evaluate this queryset
        # anyway and it gets cached so it'll only have one query in the end.
        if len(self.fields["locales"].queryset) < 2:
            self.fields["select_all"].widget = forms.HiddenInput()


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
            # Create translation if it doesn't exist yet, re-enable if translation was disabled
            # Note that the form won't show this locale as an option if the translation existed
            # in this langauge, so this shouldn't overwrite any unmanaged translations.
            translation, created = Translation.objects.update_or_create(
                source=source,
                target_locale=target_locale,
                defaults={
                    'enabled': True
                }
            )

            try:
                translation.save_target(user=self.user)
            except ValidationError:
                pass


class SubmitTranslationView(SingleObjectMixin, TemplateView):
    template_name = "wagtail_localize/admin/submit_translation.html"
    title = __("Translate")

    def get_title(self):
        return self.title

    def get_subtitle(self):
        return str(self.object)

    def get_form(self):
        if self.request.method == 'POST':
            return SubmitTranslationForm(self.object, self.request.POST)
        else:
            initial = None
            if self.request.GET.get('select_locale', None):
                select_locale = Locale.objects.filter(language_code=self.request.GET['select_locale']).first()
                if select_locale:
                    initial = {'locales': [select_locale]}

            return SubmitTranslationForm(self.object, initial=initial)

    def get_success_url(self):
        return get_valid_next_url_from_request(self.request)

    def get_default_success_url(self):
        pass

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "form": self.get_form(),
            "next_url": self.get_success_url(),
            "back_url": self.get_success_url() or self.get_default_success_url(),
        })
        return context

    def post(self, request, **kwargs):
        form = self.get_form()

        if form.is_valid():
            with transaction.atomic():
                translator = TranslationCreator(self.request.user, form.cleaned_data["locales"])
                translator.create_translations(self.object)

                # Now add the sub tree (if the obj is a page)
                if isinstance(self.object, Page):
                    if form.cleaned_data["include_subtree"]:
                        def _walk(current_page):
                            for child_page in current_page.get_children():
                                translator.create_translations(child_page)

                                if child_page.numchild:
                                    _walk(child_page)

                        _walk(self.object)

                if len(form.cleaned_data["locales"]) == 1:
                    locales = form.cleaned_data["locales"][0].get_display_name()

                else:
                    # Note: always plural
                    locales = _('{} locales').format(len(form.cleaned_data["locales"]))

                # TODO: Button that links to page in translations report when we have it
                messages.success(
                    self.request, self.get_success_message(locales)
                )

                return redirect(self.get_success_url() or self.get_default_success_url())

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perms(['wagtail_localize.submit_translation']):
            raise PermissionDenied

        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)


class SubmitPageTranslationView(SubmitTranslationView):
    title = __("Translate page")

    def get_subtitle(self):
        return self.object.get_admin_display_title()

    def get_object(self):
        page = get_object_or_404(Page, id=self.kwargs['page_id']).specific

        # Can't translate the root page
        if page.is_root():
            raise Http404

        return page

    def get_default_success_url(self):
        return reverse("wagtailadmin_explore", args=[self.get_object().get_parent().id])

    def get_success_message(self, locales):
        return _("The page '{page_title}' was successfully submitted for translation into {locales}").format(
            page_title=self.object.get_admin_display_title(),
            locales=locales
        )


class SubmitSnippetTranslationView(SubmitTranslationView):

    def get_title(self):
        return _("Translate {model_name}").format(
            model_name=self.object._meta.verbose_name
        )

    def get_object(self):
        model = get_snippet_model_from_url_params(self.kwargs['app_label'], self.kwargs['model_name'])

        if not issubclass(model, TranslatableMixin):
            raise Http404

        return get_object_or_404(model, pk=unquote(self.kwargs['pk']))

    def get_default_success_url(self):
        return reverse("wagtailsnippets:edit", args=[self.kwargs['app_label'], self.kwargs['model_name'], self.kwargs['pk']])

    def get_success_message(self, locales):
        return _("The {model_name} '{object}' was successfully submitted for translation into {locales}").format(
            model_name=self.object._meta.verbose_name,
            object=str(self.object),
            locales=locales
        )
