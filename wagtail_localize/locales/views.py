import functools

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin import messages
from wagtail.admin.edit_handlers import (
    ObjectList,
    extract_panel_definitions_from_model_class,
)
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.core.models import Locale
from wagtail.core.permissions import locale_permission_policy

from wagtail_localize.components import BaseComponentManager

from .components import LocaleComponentModelForm, get_locale_components
from .forms import LocaleForm
from .utils import get_locale_usage


@functools.lru_cache()
def get_locale_component_edit_handler(model):
    if hasattr(model, "edit_handler"):
        # use the edit handler specified on the class
        return model.edit_handler
    else:
        panels = extract_panel_definitions_from_model_class(model, exclude=["locale"])
        return ObjectList(
            panels,
            base_form_class=getattr(model, "base_form_class", LocaleComponentModelForm),
        )


class ComponentManager(BaseComponentManager):
    @classmethod
    def get_components(cls):
        return get_locale_components()

    @classmethod
    def get_component_edit_handler(cls, component_model):
        return get_locale_component_edit_handler(component_model)

    @classmethod
    def get_component_instance(cls, component_model, source_object_instance=None):
        return component_model.objects.filter(locale=source_object_instance).first()

    def is_valid(self, locale, *args, **kwargs):
        is_valid = True

        for component, _component_instance, component_form in self.components:
            if component["required"] or component_form["enabled"].value():
                component_form.full_clean()

                try:
                    component_form.validate_with_locale(locale)
                except ValidationError as e:
                    component_form.add_error(None, e)

                if not component_form.is_valid():
                    is_valid = False

        return is_valid

    def save(self, locale, *args, **kwargs):
        for component, component_instance, component_form in self.components:
            if component["required"] or component_form["enabled"].value():
                component_instance = component_form.save(commit=False)
                component_instance.locale = locale
                component_instance.save()

            elif component_instance:
                component_instance.delete()


class IndexView(generic.IndexView):
    template_name = "wagtaillocales/index.html"
    page_title = gettext_lazy("Locales")
    add_item_label = gettext_lazy("Add a locale")
    context_object_name = "locales"
    queryset = Locale.all_objects.all()

    def get_context_data(self):
        context = super().get_context_data()

        for locale in context["locales"]:
            locale.num_pages, locale.num_others = get_locale_usage(locale)

        return context


class CreateView(generic.CreateView):
    page_title = gettext_lazy("Add locale")
    success_message = gettext_lazy("Locale '{0}' created.")
    template_name = "wagtaillocales/create.html"

    def get_components(self):
        return ComponentManager.from_request(self.request)

    def get(self, request, *args, **kwargs):
        self.object = None
        self.components = self.get_components()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = None
        self.components = self.get_components()
        form = self.get_form()

        if form.is_valid() and self.components.is_valid(form.save(commit=False)):
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        self.components.save(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["components"] = self.components
        return context


class EditView(generic.EditView):
    success_message = gettext_lazy("Locale '{0}' updated.")
    error_message = gettext_lazy("The locale could not be saved due to errors.")
    delete_item_label = gettext_lazy("Delete locale")
    context_object_name = "locale"
    template_name = "wagtaillocales/edit.html"
    queryset = Locale.all_objects.all()

    def get_components(self):
        return ComponentManager.from_request(
            self.request, source_object_instance=self.object
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.components = self.get_components()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.components = self.get_components()
        form = self.get_form()

        if form.is_valid() and self.components.is_valid(form.save(commit=False)):
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        self.components.save(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["components"] = self.components
        return context


class DeleteView(generic.DeleteView):
    success_message = gettext_lazy("Locale '{0}' deleted.")
    cannot_delete_message = gettext_lazy(
        "This locale cannot be deleted because there are pages and/or other objects using it."
    )
    page_title = gettext_lazy("Delete locale")
    confirmation_message = gettext_lazy("Are you sure you want to delete this locale?")
    template_name = "wagtaillocales/confirm_delete.html"
    queryset = Locale.all_objects.all()

    def can_delete(self, locale):
        return get_locale_usage(locale) == (0, 0)

    def get_context_data(self, object=None):
        context = super().get_context_data()
        context["can_delete"] = self.can_delete(object)
        return context

    if WAGTAIL_VERSION >= (2, 16):

        def form_valid(self, form):
            if self.can_delete(self.get_object()):
                return super().form_valid(form)
            else:
                messages.error(self.request, self.cannot_delete_message)
                return super().get(self.request)

    else:

        def delete(self, request, *args, **kwargs):
            if self.can_delete(self.get_object()):
                return super().delete(request, *args, **kwargs)
            else:
                messages.error(request, self.cannot_delete_message)
                return super().get(request)


class LocaleViewSet(ModelViewSet):
    icon = "site"
    model = Locale
    permission_policy = locale_permission_policy

    index_view_class = IndexView
    add_view_class = CreateView
    edit_view_class = EditView
    delete_view_class = DeleteView

    def get_form_class(self, for_update=False):
        return LocaleForm
