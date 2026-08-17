import contextlib

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.utils import quote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.models import Page
from wagtail.snippets.models import get_snippet_models
from wagtail.utils.version import get_main_version

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.models import TranslationSource
from wagtail_localize.views.edit_translation import apply_machine_translation
from wagtail_localize.views.submit_translations import TranslationComponentManager


class UpdateTranslationsForm(forms.Form):
    publish_translations = forms.BooleanField(
        label=gettext_lazy("Publish immediately"),
        required=False,
    )
    _has_machine_translator = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_machine_translator = get_machine_translator() is not None

        if self._has_machine_translator:
            self.fields["publish_translations"].help_text = gettext_lazy(
                "Apply the updates and publish immediately. The changes will use "
                "the original language until translated unless you also select "
                '"Use machine translation".'
            )
            self.fields["use_machine_translation"] = forms.BooleanField(
                label=gettext_lazy("Use machine translation"),
                help_text=gettext_lazy(
                    "Apply machine translations to the incoming changes."
                ),
                required=False,
            )
        else:
            self.fields["publish_translations"].help_text = gettext_lazy(
                "Apply the updates and publish immediately. The changes will use "
                "the original language until translated."
            )


class UpdateTranslationsView(SingleObjectMixin, TemplateView):
    template_name = "wagtail_localize/admin/update_translations.html"
    title = gettext_lazy("Update existing translations")

    def get_object(self):
        return get_object_or_404(
            TranslationSource, id=self.kwargs["translation_source_id"]
        )

    def get_title(self):
        return self.title

    def get_subtitle(self):
        return self.object.object_repr

    def get_form(self):
        if self.request.method == "POST":
            return UpdateTranslationsForm(self.request.POST)
        else:
            return UpdateTranslationsForm()

    def get_success_message(self):
        return _("Successfully updated translations for '{object}'").format(
            object=self.object.object_repr
        )

    def get_success_url(self):
        return get_valid_next_url_from_request(self.request)

    def get_default_success_url(self):
        instance = self.object.get_source_instance()

        if isinstance(instance, Page):
            return reverse("wagtailadmin_explore", args=[instance.get_parent().id])

        elif instance._meta.model in get_snippet_models():
            return reverse(
                f"wagtailsnippets_{instance._meta.app_label}_{instance._meta.model_name}:edit",
                args=[quote(instance.pk)],
            )

        elif "wagtail_localize.modeladmin" in settings.INSTALLED_APPS:
            return reverse(
                f"{instance._meta.app_label}_{instance._meta.model_name}_modeladmin_index"
            )

    def get_edit_url(self, instance):
        if isinstance(instance, Page):
            return reverse("wagtailadmin_pages:edit", args=[instance.id])

        elif instance._meta.model in get_snippet_models():
            return reverse(
                f"wagtailsnippets_{instance._meta.app_label}_{instance._meta.model_name}:edit",
                args=[quote(instance.pk)],
            )

        elif "wagtail_localize.modeladmin" in settings.INSTALLED_APPS:
            return reverse(
                f"{instance._meta.app_label}_{instance._meta.model_name}_modeladmin_edit",
                args=[quote(instance.pk)],
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "translations": [
                    {
                        "title": str(translation.get_target_instance()),
                        "locale": translation.target_locale,
                        "edit_url": self.get_edit_url(
                            translation.get_target_instance()
                        ),
                    }
                    for translation in self.object.translations.filter(
                        enabled=True
                    ).select_related("target_locale")
                ],
                "last_sync_date": self.object.last_updated_at,
                "form": self.get_form(),
                "next_url": self.get_success_url(),
                "back_url": self.get_success_url() or self.get_default_success_url(),
                "components": self.components,
                "wagtail_version": get_main_version(),
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
        self.object.update_from_db()

        enabled_translations = self.object.translations.filter(enabled=True)
        if form.cleaned_data.get("use_machine_translation"):
            machine_translator = get_machine_translator()
            for translation in enabled_translations.select_related("target_locale"):
                apply_machine_translation(
                    translation.id, self.request.user, machine_translator
                )

        if form.cleaned_data["publish_translations"]:
            for translation in enabled_translations.select_related("target_locale"):
                with contextlib.suppress(ValidationError):
                    translation.save_target(user=self.request.user, publish=True)
        else:
            for translation in enabled_translations.select_related(
                "source", "target_locale"
            ):
                with contextlib.suppress(ValidationError):
                    translation.source.update_target_view_restrictions(
                        translation.target_locale
                    )

        self.components.save(
            self.object,
            sources_and_translations={self.object: list(enabled_translations)},
        )

        # TODO: Button that links to page in translations report when we have it
        messages.success(self.request, self.get_success_message())

        return redirect(self.get_success_url() or self.get_default_success_url())

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perms(["wagtail_localize.submit_translation"]):
            raise PermissionDenied

        self.object = self.get_object()
        self.components = TranslationComponentManager.from_request(
            self.request, source_object_instance=self.object
        )
        return super().dispatch(request, *args, **kwargs)
