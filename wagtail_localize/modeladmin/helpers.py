from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.contrib.modeladmin.helpers import ButtonHelper, PageButtonHelper
from wagtail.contrib.modeladmin.views import InspectView
from wagtail.core.models import Locale, Page, TranslatableMixin

from wagtail_localize.models import TranslationSource


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
                "wagtail_localize_modeladmin:submit_translation",
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
                "label": _("Sync translated %(model_name)s")
                % {"model_name": obj._meta.verbose_name_plural},
                "classname": classname,
                "title": _("Sync translated %(model_name)s")
                % {"model_name": obj._meta.verbose_name_plural},
            }
