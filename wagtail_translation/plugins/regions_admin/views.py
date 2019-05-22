from django.db import transaction
from django.utils.translation import ugettext_lazy

from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_translation.models import Region
from .forms import RegionForm


class IndexView(generic.IndexView):
    template_name = 'wagtail_translation_regions_admin/index.html'
    page_title = ugettext_lazy("Regions")
    add_item_label = ugettext_lazy("Add a region")
    context_object_name = 'regions'


class CreateView(generic.CreateView):
    page_title = ugettext_lazy("Add region")
    success_message = ugettext_lazy("Region '{0}' created.")
    template_name = 'wagtail_translation_regions_admin/create.html'


class EditView(generic.EditView):
    success_message = ugettext_lazy("Region '{0}' updated.")
    error_message = ugettext_lazy("The site could not be saved due to errors.")
    delete_item_label = ugettext_lazy("Delete region")
    context_object_name = 'region'
    template_name = 'wagtail_translation_regions_admin/edit.html'


class DeleteView(generic.DeleteView):
    success_message = ugettext_lazy("Region '{0}' deleted.")
    page_title = ugettext_lazy("Delete region")
    confirmation_message = ugettext_lazy("Are you sure you want to delete this region?")


class RegionViewSet(ModelViewSet):
    icon = 'site'
    model = Region
    permission_policy = ModelPermissionPolicy(Region)

    index_view_class = IndexView
    add_view_class = CreateView
    edit_view_class = EditView
    delete_view_class = DeleteView

    def get_form_class(self, for_update=False):
        return RegionForm
