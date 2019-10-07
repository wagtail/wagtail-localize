import functools

from wagtail.admin.edit_handlers import (
    ObjectList,
    extract_panel_definitions_from_model_class,
)


REGION_COMPONENTS = []


def get_region_components():
    return REGION_COMPONENTS


def register_region_component(model):
    if model not in REGION_COMPONENTS:
        REGION_COMPONENTS.append(model)
        REGION_COMPONENTS.sort(key=lambda x: x._meta.verbose_name)

    return model


@functools.lru_cache()
def get_region_component_edit_handler(model):
    if hasattr(model, "edit_handler"):
        # use the edit handler specified on the class
        return model.edit_handler
    else:
        panels = extract_panel_definitions_from_model_class(model, exclude=["region"])
        return ObjectList(panels)
