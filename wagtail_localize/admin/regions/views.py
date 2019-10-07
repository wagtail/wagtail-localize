from django.db import transaction
from django.utils.translation import ugettext_lazy

from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.models import Region
from .components import get_region_components, get_region_component_edit_handler
from .forms import RegionForm


class RegionComponentManager:
    def __init__(self, components):
        self.components = components

    @classmethod
    def from_request(cls, request, instance=None):
        components = []

        for component_model in get_region_components():
            component_instance = component_model.objects.filter(region=instance).first()
            edit_handler = get_region_component_edit_handler(component_model).bind_to(
                model=component_model, instance=component_instance, request=request
            )
            form_class = edit_handler.get_form_class()
            prefix = "component_{}_{}".format(
                component_model._meta.app_label, component_model.__name__
            )

            if request.method == "POST":
                form = form_class(
                    request.POST,
                    request.FILES,
                    instance=component_instance,
                    prefix=prefix,
                )
            else:
                form = form_class(instance=component_instance, prefix=prefix)

            components.append((component_model, component_instance, form))

        return cls(components)

    def is_valid(self):
        return all(
            component_form.is_valid()
            for component_model, component_instance, component_form in self.components
        )

    def save(self, region):
        for component_model, component_instance, component_form in self.components:
            component_instance = component_form.save(commit=False)
            component_instance.region = region
            component_instance.save()

    def __iter__(self):
        return iter(self.components)


class IndexView(generic.IndexView):
    template_name = "wagtail_localize_regions_admin/index.html"
    page_title = ugettext_lazy("Regions")
    add_item_label = ugettext_lazy("Add a region")
    context_object_name = "regions"


class CreateView(generic.CreateView):
    page_title = ugettext_lazy("Add region")
    success_message = ugettext_lazy("Region '{0}' created.")
    template_name = "wagtail_localize_regions_admin/create.html"

    def get_components(self):
        return RegionComponentManager.from_request(self.request)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        self.components = RegionComponentManager.from_request(self.request)

        if form.is_valid() and self.get_components().is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        self.get_components().save(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["components"] = self.get_components()
        return context


class EditView(generic.EditView):
    success_message = ugettext_lazy("Region '{0}' updated.")
    error_message = ugettext_lazy("The site could not be saved due to errors.")
    delete_item_label = ugettext_lazy("Delete region")
    context_object_name = "region"
    template_name = "wagtail_localize_regions_admin/edit.html"

    def get_components(self):
        return RegionComponentManager.from_request(self.request, instance=self.object)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        if form.is_valid() and self.get_components().is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        self.get_components().save(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["components"] = self.get_components()
        return context


class DeleteView(generic.DeleteView):
    success_message = ugettext_lazy("Region '{0}' deleted.")
    page_title = ugettext_lazy("Delete region")
    confirmation_message = ugettext_lazy("Are you sure you want to delete this region?")


class RegionViewSet(ModelViewSet):
    icon = "site"
    model = Region
    permission_policy = ModelPermissionPolicy(Region)

    index_view_class = IndexView
    add_view_class = CreateView
    edit_view_class = EditView
    delete_view_class = DeleteView

    def get_form_class(self, for_update=False):
        return RegionForm
