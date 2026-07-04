try:
    from wagtail_modeladmin.options import (
        ModelAdmin,
        ModelAdminGroup,
        modeladmin_register,
    )
except ImportError:
    from wagtail.contrib.modeladmin.options import (
        ModelAdmin,
        ModelAdminGroup,
        modeladmin_register,
    )

from wagtail_localize.modeladmin.options import TranslatableModelAdmin

from .models import NonTranslatableModel, TestModel, TestPage


class TestPageAdmin(TranslatableModelAdmin):
    model = TestPage


class TestModelAdmin(TranslatableModelAdmin):
    model = TestModel
    inspect_view_enabled = True
    list_export = ["title", "test_charfield", "test_textfield", "test_emailfield"]


class NonTranslatableModelAdmin(ModelAdmin):
    model = NonTranslatableModel


@modeladmin_register
class ModelAdminAdmin(ModelAdminGroup):
    items = (TestPageAdmin, TestModelAdmin, NonTranslatableModelAdmin)
    menu_label = "Model Admin"
