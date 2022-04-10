import functools
import inspect

from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin.forms import WagtailAdminModelForm


try:
    from wagtail.admin.panels import (
        ObjectList,
        extract_panel_definitions_from_model_class,
    )
except ImportError:
    from wagtail.admin.edit_handlers import (
        ObjectList,
        extract_panel_definitions_from_model_class,
    )

TRANSLATION_COMPONENTS = []


def get_translation_components():
    return TRANSLATION_COMPONENTS


def register_translation_component(
    *, heading, help_text=None, required=False, enable_text=None, disable_text=None
):
    def _wrapper(model):
        if model not in TRANSLATION_COMPONENTS:
            TRANSLATION_COMPONENTS.append(
                {
                    "heading": heading,
                    "help_text": help_text,
                    "required": required,
                    "model": model,
                    "slug": model._meta.db_table,
                    "enable_text": enable_text,
                    "disable_text": disable_text or _("Disable"),
                }
            )
            TRANSLATION_COMPONENTS.sort(key=lambda x: x["model"]._meta.verbose_name)

        return model

    return _wrapper


def accepts_parameter(func, param):
    """
    Determine whether the callable `func` has a signature that accepts the given parameter
    """
    signature = inspect.signature(func)
    return param in signature.parameters


class BaseComponentManager:
    def __init__(self, components):
        self.components = components

    @classmethod
    def get_components(cls):
        raise NotImplementedError

    @classmethod
    def get_component_edit_handler(cls, component_model):
        raise NotImplementedError

    @classmethod
    def get_component_instance(cls, component_model, source_object_instance=None):
        raise NotImplementedError

    @classmethod
    def from_request(cls, request, source_object_instance=None):
        components = []

        for component in cls.get_components():
            component_model = component["model"]

            component_instance = cls.get_component_instance(
                component_model, source_object_instance=source_object_instance
            )
            edit_handler = cls.get_component_edit_handler(component_model)

            if WAGTAIL_VERSION >= (3, 0):
                edit_handler = edit_handler.bind_to_model(component_model)
            else:
                edit_handler = edit_handler.bind_to(
                    model=component_model, instance=component_instance, request=request
                )
            form_class = edit_handler.get_form_class()

            # Add an 'enabled' field to the form if it isn't required
            if not component["required"]:
                form_class = type(
                    form_class.__name__,
                    (form_class,),
                    {
                        "enabled": forms.BooleanField(
                            initial=component_instance is not None
                        ),
                        # Move enabled field to top
                        "field_order": ["enabled"],
                    },
                )

            prefix = "component-{}".format(component_model._meta.db_table)

            form_kwargs = {
                "instance": component_instance,
                "prefix": prefix,
            }
            if accepts_parameter(form_class, "source_object_instance"):
                form_kwargs["source_object_instance"] = source_object_instance
            if accepts_parameter(form_class, "user"):
                form_kwargs["user"] = request.user

            if request.method == "POST":
                form = form_class(request.POST, request.FILES, **form_kwargs)
            else:
                form = form_class(**form_kwargs)

            components.append((component, component_instance, form))

        return cls(components)

    def is_valid(self, *args, **kwargs):
        is_valid = True

        for component, _component_instance, component_form in self.components:
            if component["required"] or component_form["enabled"].value():
                component_form.full_clean()

                if not component_form.is_valid():
                    is_valid = False

        return is_valid

    def save(self, *args, **kwargs):
        for component, component_instance, component_form in self.components:
            if component["required"] or component_form["enabled"].value():
                component_form.save()
            elif component_instance:
                component_instance.delete()

    def __iter__(self):
        return iter(self.components)


@functools.lru_cache()
def get_translation_component_edit_handler(model):
    if hasattr(model, "edit_handler"):
        # use the edit handler specified on the class
        return model.edit_handler
    else:
        panels = extract_panel_definitions_from_model_class(model)
        return ObjectList(
            panels,
            base_form_class=getattr(model, "base_form_class", WagtailAdminModelForm),
        )


class TranslationComponentManager(BaseComponentManager):
    """
    The translation component manager handles all registered components for translation.

    Classes registered as translation components should implement a
    `get_or_create_from_source_and_translation_data` method which takes
    `translation_source`, `translations` and kwargs as parameters.
    """

    @classmethod
    def get_components(cls):
        return get_translation_components()

    @classmethod
    def get_component_edit_handler(cls, component_model):
        return get_translation_component_edit_handler(component_model)

    @classmethod
    def get_component_instance(cls, component_model, source_object_instance=None):
        return None

    def save(self, source_object_instance, sources_and_translations=None):
        for component, component_instance, component_form in self.components:
            if component["required"] or component_form["enabled"].value():
                if hasattr(
                    component["model"], "get_or_create_from_source_and_translation_data"
                ):
                    component_instance = component_form.save(commit=False)
                    data = self._get_component_form_data(
                        component_instance, component_form.cleaned_data
                    )

                    self._save_component_instances(
                        component["model"], sources_and_translations, **data
                    )
                else:
                    component_form.save()

    def _get_component_form_data(self, component_instance, cleaned_data):
        return {
            field.name: getattr(component_instance, field.name)
            for field in component_instance._meta.get_fields()
            if field.name in cleaned_data
        }

    def _save_component_instances(
        self, component_model, sources_and_translations, **kwargs
    ):
        for translation_source, translations in sources_and_translations.items():
            try:
                component_model.get_or_create_from_source_and_translation_data(
                    translation_source, translations, **kwargs
                )
            except TypeError:
                continue
