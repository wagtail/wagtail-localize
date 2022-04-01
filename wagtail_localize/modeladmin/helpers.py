from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.contrib.modeladmin.helpers import (
    AdminURLHelper,
    ButtonHelper,
    PageAdminURLHelper,
    PageButtonHelper,
    PagePermissionHelper,
    PermissionHelper,
)
from wagtail.contrib.modeladmin.views import InspectView
from wagtail.core.models import Locale, Page, TranslatableMixin

from wagtail_localize.models import TranslationSource


class TranslatablePermissionHelper(PermissionHelper):
    def __init__(self, model, inspect_view_enabled=False):
        super().__init__(model, inspect_view_enabled)
        self.locale = None


class TranslatablePagePermissionHelper(
    TranslatablePermissionHelper,
    PagePermissionHelper,
):
    def get_valid_parent_pages(self, user):
        parents = super().get_valid_parent_pages(user)
        if self.locale:
            parents = parents.filter(locale_id=self.locale.id)
        return parents


class TranslatableAdminURLHelper(AdminURLHelper):
    def __init__(self, model):
        super().__init__(model)
        self.locale = None

    def get_action_url(self, action, *args, **kwargs):
        locale = kwargs.pop("locale", self.locale)
        url = super().get_action_url(action, *args, **kwargs)
        if locale and action in ("create", "choose_parent", "index"):
            url += f"?locale={locale.language_code}"
        return url

    @property
    def index_url(self):
        return self.get_action_url("index")

    @property
    def create_url(self):
        return self.get_action_url("create")


class TranslatablePageAdminURLHelper(TranslatableAdminURLHelper, PageAdminURLHelper):
    pass


class TranslatableButtonHelper(ButtonHelper):
    def get_buttons_for_obj(self, obj, **kwargs):
        btns = super().get_buttons_for_obj(obj, **kwargs)
        user = self.request.user
        next_url = self.request.get_full_path()
        if isinstance(self.view, InspectView):
            classname = "button button-secondary"
        else:
            classname = "button button-secondary button-small"
        btns += list(get_translation_buttons(obj, user, next_url, classname))
        return btns


class TranslatablePageButtonHelper(TranslatableButtonHelper, PageButtonHelper):
    pass


def get_translation_buttons(obj, user, next_url=None, classname=""):
    """
    Generate listing buttons for translating/syncing objects in modeladmin.
    """
    model = type(obj)

    if issubclass(model, TranslatableMixin) and user.has_perm(
        "wagtail_localize.submit_translation"
    ):

        # If there's at least one locale that we haven't translated into yet, show "Translate" button
        if isinstance(obj, Page):
            has_locale_to_translate_to = Locale.objects.exclude(
                id__in=obj.get_translations(inclusive=True)
                .exclude(alias_of__isnull=False)
                .values_list("locale_id", flat=True)
            ).exists()
        else:
            has_locale_to_translate_to = Locale.objects.exclude(
                id__in=obj.get_translations(inclusive=True).values_list(
                    "locale_id", flat=True
                )
            ).exists()

        if has_locale_to_translate_to:
            url = reverse(
                "wagtail_localize:submit_modeladmin_translation",
                args=[model._meta.app_label, model._meta.model_name, quote(obj.pk)],
            )
            yield {
                "url": url,
                "label": _("Translate"),
                "classname": classname,
                "title": _("Translate"),
            }

        # If the object is the source for translations, show "Sync translated" button
        source = TranslationSource.objects.get_for_instance_or_none(obj)
        if source is not None and source.translations.filter(enabled=True).exists():
            url = reverse("wagtail_localize:update_translations", args=[source.id])
            if next_url is not None:
                url += "?" + urlencode({"next": next_url})

            yield {
                "url": url,
                "label": _("Sync translated %s") % obj._meta.verbose_name_plural,
                "classname": classname,
                "title": _("Sync translated %s") % obj._meta.verbose_name_plural,
            }
