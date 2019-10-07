from django.db import transaction
from django.utils.translation import ugettext_lazy

from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from .forms import SiteForm, SiteLanguageFormSet
from .models import Site


class IndexView(generic.IndexView):
    template_name = "wagtail_localize_sites/index.html"
    page_title = ugettext_lazy("Sites")
    add_item_label = ugettext_lazy("Add a site")
    context_object_name = "sites"


class CreateView(generic.CreateView):
    page_title = ugettext_lazy("Add site")
    success_message = ugettext_lazy("Site '{0}' created.")
    template_name = "wagtail_localize_sites/create.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)

        if self.request.POST:
            data["languages_formset"] = SiteLanguageFormSet(self.request.POST)
        else:
            data["languages_formset"] = SiteLanguageFormSet()

        return data


class EditView(generic.EditView):
    success_message = ugettext_lazy("Site '{0}' updated.")
    error_message = ugettext_lazy("The site could not be saved due to errors.")
    delete_item_label = ugettext_lazy("Delete site")
    context_object_name = "site"
    template_name = "wagtail_localize_sites/edit.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)

        if self.request.POST:
            data["languages_formset"] = SiteLanguageFormSet(
                self.request.POST, instance=self.object
            )
        else:
            data["languages_formset"] = SiteLanguageFormSet(instance=self.object)

        return data


class DeleteView(generic.DeleteView):
    success_message = ugettext_lazy("Site '{0}' deleted.")
    page_title = ugettext_lazy("Delete site")
    confirmation_message = ugettext_lazy("Are you sure you want to delete this site?")


class SiteViewSet(ModelViewSet):
    icon = "site"
    model = Site
    permission_policy = ModelPermissionPolicy(Site)

    index_view_class = IndexView
    add_view_class = CreateView
    edit_view_class = EditView
    delete_view_class = DeleteView

    def get_form_class(self, for_update=False):
        return SiteForm
