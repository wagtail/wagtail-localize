from django import forms


TRANSLATION_COMPONENTS = []


def get_translation_components():
    return TRANSLATION_COMPONENTS


def register_translation_component(*, heading, help_text=None, required=False):
    def _wrapper(model):
        if model not in TRANSLATION_COMPONENTS:
            TRANSLATION_COMPONENTS.append(
                {
                    "heading": heading,
                    "help_text": help_text,
                    "required": required,
                    "model": model,
                    "slug": model._meta.db_table,
                }
            )
            TRANSLATION_COMPONENTS.sort(key=lambda x: x["model"]._meta.verbose_name)

        return model

    return _wrapper


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
    def from_request(cls, request, instance=None):
        components = []

        for component in cls.get_components():
            component_model = component["model"]

            component_instance = component_model.objects.filter(locale=instance).first()
            edit_handler = cls.get_component_edit_handler(component_model).bind_to(
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

            if request.method == "POST":
                form = form_class(
                    request.POST,
                    request.FILES,
                    instance=component_instance,
                    prefix=prefix,
                )
            else:
                form = form_class(instance=component_instance, prefix=prefix)

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
