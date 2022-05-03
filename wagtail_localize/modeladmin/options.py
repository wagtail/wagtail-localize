from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from wagtail.contrib.modeladmin.options import ModelAdmin
from wagtail.core.models import TranslatableMixin

from .helpers import TranslatableButtonHelper, TranslatablePageButtonHelper
from .views import (
    TranslatableChooseParentView,
    TranslatableCreateView,
    TranslatableDeleteView,
    TranslatableEditView,
    TranslatableHistoryView,
    TranslatableIndexView,
    TranslatableInspectView,
)


class TranslatableModelAdmin(ModelAdmin):
    index_view_class = TranslatableIndexView
    create_view_class = TranslatableCreateView
    edit_view_class = TranslatableEditView
    inspect_view_class = TranslatableInspectView
    delete_view_class = TranslatableDeleteView
    history_view_class = TranslatableHistoryView
    choose_parent_view_class = TranslatableChooseParentView

    def __init__(self, parent=None):
        super().__init__(parent)

        if "wagtail_localize.modeladmin" not in settings.INSTALLED_APPS:
            raise ImproperlyConfigured(
                'To use the TranslatableModelAdmin class "wagtail_localize.modeladmin" '
                "must be added to your INSTALLED_APPS setting."
            )

        if not issubclass(self.model, TranslatableMixin):
            raise ImproperlyConfigured(
                f"Model `{self.model}` used in translatable admin `{self.__class__}` "
                f"must subclass the `{TranslatableMixin}` class."
            )

    def get_button_helper_class(self):
        if self.button_helper_class:
            return self.button_helper_class
        if self.is_pagemodel:
            return TranslatablePageButtonHelper
        return TranslatableButtonHelper

    def get_templates(self, action="index"):
        app_label = self.opts.app_label.lower()
        model_name = self.opts.model_name.lower()
        return [
            "wagtail_localize/modeladmin/%s/%s/translatable_%s.html"
            % (app_label, model_name, action),
            "wagtail_localize/modeladmin/%s/translatable_%s.html" % (app_label, action),
            "wagtail_localize/modeladmin/translatable_%s.html" % (action,),
        ]
