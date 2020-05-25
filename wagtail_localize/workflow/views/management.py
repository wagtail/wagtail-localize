from django import forms
from django.conf.urls import url
from django.contrib import messages
from django.db import transaction
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404, redirect

from wagtail.admin.views import generic
from wagtail.admin.viewsets.base import ViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.models import TranslatableMixin, TranslatablePageMixin

from ..action_modules import get_action_modules
from ..models import TranslationRequest


class TranslationRequestForm(forms.ModelForm):
    class Meta:
        model = TranslationRequest
        fields = ["source_locale"]


class TranslationRequestListView(ListView):
    template_name = "wagtail_localize_workflow/management/list.html"
    page_title = ugettext_lazy("Translaton requests")
    context_object_name = "translation_requests"
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    header_icon = ""


class TranslationRequestDetailView(DetailView):
    success_message = ugettext_lazy("Translation request '{0}' updated.")
    error_message = ugettext_lazy(
        "The translation request could not be saved due to errors."
    )
    context_object_name = "translation_request"
    template_name = "wagtail_localize_workflow/management/detail.html"
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    copy_for_translation_url_name = None
    header_icon = ""

    def get_context_data(self, object):
        context = super().get_context_data(object=object)

        revisions_by_page_model = {}
        revisions_by_other_model = {}

        for revision in object.revisions.all().select_related('object'):
            model = revision.object.content_type.model_class()
            if issubclass(model, TranslatablePageMixin):
                if model not in revisions_by_page_model:
                    revisions_by_page_model[model] = []

                revisions_by_page_model[model].append(revision)

            elif issubclass(model, TranslatableMixin):
                if model not in revisions_by_other_model:
                    revisions_by_other_model[model] = []

                revisions_by_other_model[model].append(revision)

        pages = []
        for model, revisions in revisions_by_page_model.items():
            pages.extend(model.objects.filter(locale=object.source_locale, translation_key__in=[revision.object_id for revision in revisions]))
        pages.sort(key=lambda page: page.path)
        context["pages"] = pages

        other_models = []
        for model, revisions in revisions_by_other_model.items():
            other_models.append((model._meta.verbose_name_plural, model.objects.filter(locale=object.source_locale, translation_key__in=[revision.object_id for revision in revisions])))
        context["other_models"] = other_models

        context["action_modules"] = [
            action_module(self.request, object)
            for action_module in get_action_modules()
        ]

        # Hide action modules if their is_shown method returns false
        context["action_modules"] = [
            action_module
            for action_module in context["action_modules"]
            if action_module.is_shown()
        ]

        return context


@require_POST
def copy_pages(request, translation_request_id):
    translation_request = get_object_or_404(
        TranslationRequest, id=translation_request_id
    )
    num_copied = 0

    for page in translation_request.pages.filter(is_completed=False):
        instance = page.source_revision.as_page_object()

        if instance.has_translation(translation_request.target_locale):
            continue

        with transaction.atomic():
            new_page = instance.copy_for_translation(translation_request.target_locale)

            # Update translation request
            page.is_completed = True
            page.completed_revision = new_page.get_latest_revision()
            page.save(update_fields=["is_completed", "completed_revision"])

        num_copied += 1

    # TODO: Plural
    messages.success(request, "%d pages successfully copied" % num_copied)

    return redirect(
        "wagtail_localize_workflow_management:detail", translation_request_id
    )


class CopyForTranslationView(DetailView):
    success_message = ugettext_lazy("Translation request '{0}' updated.")
    error_message = ugettext_lazy(
        "The translation request could not be saved due to errors."
    )
    context_object_name = "translation_request_page"
    template_name = "wagtail_localize_workflow/management/copy_for_translation.html"
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    copy_for_translation_url_name = None
    header_icon = ""

    def get_object(self):
        translation_request = super().get_object()
        return get_object_or_404(
            translation_request.pages.all(), id=self.kwargs["page_id"]
        )

    def post(self, request, *args, **kwargs):
        translation_request_page = self.get_object()

        new_page = translation_request_page.source_page.specific.copy_for_translation(
            translation_request_page.request.target_locale
        )
        translation_request_page.is_completed = True
        translation_request_page.completed_revision = new_page.get_latest_revision()
        translation_request_page.save(
            update_fields=["is_completed", "completed_revision"]
        )
        return redirect("wagtailadmin_pages:edit", new_page.id)


class TranslationRequestViewSet(ViewSet):
    icon = "site"

    model = TranslationRequest
    permission_policy = ModelPermissionPolicy(TranslationRequest)

    list_view_class = TranslationRequestListView
    detail_view_class = TranslationRequestDetailView
    copy_for_translation_view_class = CopyForTranslationView

    @property
    def list_view(self):
        return self.list_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name("list"),
            detail_url_name=self.get_url_name("detail"),
            header_icon=self.icon,
        )

    @property
    def detail_view(self):
        return self.detail_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name("list"),
            detail_url_name=self.get_url_name("detail"),
            copy_for_translation_url_name=self.get_url_name("copy_for_translation"),
            header_icon=self.icon,
        )

    @property
    def copy_for_translation_view(self):
        return self.copy_for_translation_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name("list"),
            detail_url_name=self.get_url_name("detail"),
            copy_for_translation_url_name=self.get_url_name("copy_for_translation"),
            header_icon=self.icon,
        )

    def get_urlpatterns(self):
        return super().get_urlpatterns() + [
            url(r"^$", self.list_view, name="list"),
            url(r"^(?P<pk>\d+)/$", self.detail_view, name="detail"),
            url(r"^(\d+)/copy_pages/$", copy_pages, name="copy_pages"),
            url(
                r"^(?P<pk>\d+)/copy_for_translation/(?P<page_id>\d+)/$",
                self.copy_for_translation_view,
                name="copy_for_translation",
            ),
        ]
