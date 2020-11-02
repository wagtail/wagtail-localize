from django import forms

from django.contrib import messages
from django.contrib.admin.utils import quote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as __
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import Page

from wagtail_localize.models import TranslationSource


class UpdateTranslationsForm(forms.Form):
    publish_translations = forms.BooleanField(
        label=__("Publish immediately"),
        help_text=__("This will apply the updates and publish immediately, before any new translations happen."),
        required=False,
    )


class UpdateTranslationsView(SingleObjectMixin, TemplateView):
    template_name = "wagtail_localize/admin/update_translations.html"
    title = __("Update existing translations")

    def get_object(self):
        return get_object_or_404(TranslationSource, id=self.kwargs['translation_source_id'])

    def get_title(self):
        return self.title

    def get_subtitle(self):
        return self.object.object_repr

    def get_form(self):
        if self.request.method == 'POST':
            return UpdateTranslationsForm(self.request.POST)
        else:
            return UpdateTranslationsForm()

    def get_success_message(self):
        return _("Successfully updated translations for '{object}'").format(object=self.object.object_repr)

    def get_success_url(self):
        return get_valid_next_url_from_request(self.request)

    def get_default_success_url(self):
        instance = self.object.get_source_instance()

        if isinstance(instance, Page):
            return reverse("wagtailadmin_explore", args=[instance.get_parent().id])
        else:
            return reverse("wagtailsnippets:edit", args=[instance._meta.app_label, instance._meta.model_name, quote(instance.pk)])

    def get_edit_url(self, instance):
        if isinstance(instance, Page):
            return reverse("wagtailadmin_pages:edit", args=[instance.id])
        else:
            return reverse("wagtailsnippets:edit", args=[instance._meta.app_label, instance._meta.model_name, quote(instance.pk)])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "translations": [
                {
                    "title": str(translation.get_target_instance()),
                    "locale": translation.target_locale,
                    "edit_url": self.get_edit_url(translation.get_target_instance()),
                }
                for translation in self.object.translations.filter(enabled=True).select_related("target_locale")
            ],
            "last_sync_date": self.object.last_updated_at,
            "form": self.get_form(),
            "next_url": self.get_success_url(),
            "back_url": self.get_success_url() or self.get_default_success_url(),
        })
        return context

    def post(self, request, **kwargs):
        form = self.get_form()

        if form.is_valid():
            with transaction.atomic():
                self.object.update_from_db()

                if form.cleaned_data['publish_translations']:
                    for translation in self.object.translations.filter(enabled=True).select_related("target_locale"):
                        try:
                            translation.save_target(user=request.user, publish=True)
                        except ValidationError:
                            pass

                # TODO: Button that links to page in translations report when we have it
                messages.success(
                    self.request, self.get_success_message()
                )

                return redirect(self.get_success_url() or self.get_default_success_url())

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perms(['wagtail_localize.submit_translation']):
            raise PermissionDenied

        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)
