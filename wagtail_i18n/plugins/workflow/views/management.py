from django import forms
from django.conf.urls import url
from django.db import transaction
from django.utils.translation import ugettext_lazy
from django.views.generic import DetailView, ListView

from wagtail.admin.views import generic
from wagtail.admin.viewsets.base import ViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from ..models import TranslationRequest


class TranslationRequestForm(forms.ModelForm):

    class Meta:
        model = TranslationRequest
        fields = ['source_locale']


class TranslationRequestListView(ListView):
    template_name = 'wagtail_i18n_workflow/management/list.html'
    page_title = ugettext_lazy("Translaton requests")
    context_object_name = 'translation_requests'
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    header_icon = ''


class TranslationRequestDetailView(DetailView):
    success_message = ugettext_lazy("Translation request '{0}' updated.")
    error_message = ugettext_lazy("The translation request could not be saved due to errors.")
    context_object_name = 'translation_request'
    template_name = 'wagtail_i18n_workflow/management/detail.html'
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    header_icon = ''


class TranslationRequestViewSet(ViewSet):
    icon = 'site'

    model = TranslationRequest
    permission_policy = ModelPermissionPolicy(TranslationRequest)

    list_view_class = TranslationRequestListView
    detail_view_class = TranslationRequestDetailView

    @property
    def list_view(self):
        return self.list_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name('list'),
            detail_url_name=self.get_url_name('detail'),
            header_icon=self.icon,
        )

    @property
    def detail_view(self):
        return self.detail_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name('list'),
            detail_url_name=self.get_url_name('detail'),
            header_icon=self.icon,
        )

    def get_urlpatterns(self):
        return super().get_urlpatterns() + [
            url(r'^$', self.list_view, name='list'),
            url(r'^(?P<pk>\d+)/$', self.detail_view, name='detail'),
        ]
