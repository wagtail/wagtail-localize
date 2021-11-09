from django import forms


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
