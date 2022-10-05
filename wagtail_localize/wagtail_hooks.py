from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import include, path, reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.i18n import JavaScriptCatalog
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.admin.action_menu import ActionMenuItem as PageActionMenuItem
from wagtail.admin.menu import MenuItem
from wagtail.core import hooks
from wagtail.core.log_actions import LogFormatter
from wagtail.core.models import Locale, Page, TranslatableMixin
from wagtail.snippets.action_menu import ActionMenuItem as SnippetActionMenuItem
from wagtail.snippets.widgets import SnippetListingButton

# Import synctree so it can register its signal handler
from . import synctree  # noqa
from .models import Translation, TranslationSource
from .views import (
    convert,
    edit_translation,
    report,
    snippets_api,
    submit_translations,
    update_translations,
)


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path(
            "jsi18n/",
            JavaScriptCatalog.as_view(packages=["wagtail_localize"]),
            name="javascript_catalog",
        ),
        path(
            "submit/page/<int:page_id>/",
            submit_translations.SubmitPageTranslationView.as_view(),
            name="submit_page_translation",
        ),
        path(
            "submit/snippet/<slug:app_label>/<slug:model_name>/<str:pk>/",
            submit_translations.SubmitSnippetTranslationView.as_view(),
            name="submit_snippet_translation",
        ),
        path(
            "update/<int:translation_source_id>/",
            update_translations.UpdateTranslationsView.as_view(),
            name="update_translations",
        ),
        path(
            "translate/<int:translation_id>/strings/<int:string_segment_id>/edit/",
            edit_translation.edit_string_translation,
            name="edit_string_translation",
        ),
        path(
            "translate/<int:translation_id>/overrides/<int:overridable_segment_id>/edit/",
            edit_translation.edit_override,
            name="edit_override",
        ),
        path(
            "translate/<int:translation_id>/pofile/download/",
            edit_translation.download_pofile,
            name="download_pofile",
        ),
        path(
            "translate/<int:translation_id>/pofile/upload/",
            edit_translation.upload_pofile,
            name="upload_pofile",
        ),
        path(
            "translate/<int:translation_id>/machine_translate/",
            edit_translation.machine_translate,
            name="machine_translate",
        ),
        path(
            "translate/<int:translation_id>/preview/",
            edit_translation.preview_translation,
            name="preview_translation",
        ),
        path(
            "translate/<int:translation_id>/preview/<str:mode>/",
            edit_translation.preview_translation,
            name="preview_translation",
        ),
        path(
            "translate/<int:translation_id>/disable/",
            edit_translation.stop_translation,
            name="stop_translation",
        ),
        path(
            "page/<int:page_id>/convert_to_alias/",
            convert.convert_to_alias,
            name="convert_to_alias",
        ),
        path(
            "reports/translations/",
            report.TranslationsReportView.as_view(),
            name="translations_report",
        ),
        path(
            "api/snippets/<slug:app_label>/<slug:model_name>/",
            snippets_api.SnippetViewSet.as_view({"get": "list"}),
            name="snippets_api_listing",
        ),
        path(
            "api/snippets/<slug:app_label>/<slug:model_name>/<str:pk>/",
            snippets_api.SnippetViewSet.as_view({"get": "retrieve"}),
            name="snippets_api_detail",
        ),
    ]

    return [
        path(
            "localize/",
            include(
                (urls, "wagtail_localize"),
                namespace="wagtail_localize",
            ),
        )
    ]


@hooks.register("register_permissions")
def register_submit_translation_permission():
    return Permission.objects.filter(
        content_type__app_label="wagtail_localize", codename="submit_translation"
    )


if WAGTAIL_VERSION >= (4, 0, 0):

    def set_button_icon(button, icon_name):
        button.icon_name = icon_name
        return button

else:

    def set_button_icon(button, icon_name):
        return button


def page_listing_more_buttons(page, page_perms, next_url=None):
    if not page.is_root() and page_perms.user.has_perm(
        "wagtail_localize.submit_translation"
    ):
        # If there's at least one locale that we haven't translated into yet, show "Translate this page" button
        has_locale_to_translate_to = Locale.objects.exclude(
            id__in=page.get_translations(inclusive=True)
            .exclude(alias_of__isnull=False)
            .values_list("locale_id", flat=True)
        ).exists()

        if has_locale_to_translate_to:
            url = reverse("wagtail_localize:submit_page_translation", args=[page.id])

            yield set_button_icon(
                wagtailadmin_widgets.Button(_("Translate this page"), url, priority=60),
                "wagtail-localize-language",
            )

        # If the page is the source for translations, show "Sync translated pages" button
        source = TranslationSource.objects.get_for_instance_or_none(page)
        if source is not None and source.translations.filter(enabled=True).exists():
            url = reverse("wagtail_localize:update_translations", args=[source.id])
            if next_url is not None:
                url += "?" + urlencode({"next": next_url})

            yield set_button_icon(
                wagtailadmin_widgets.Button(
                    _("Sync translated pages"), url, priority=65
                ),
                "resubmit",
            )


if WAGTAIL_VERSION >= (4, 0, 0):

    hooks.register("register_page_header_buttons", page_listing_more_buttons)
    hooks.register("register_page_listing_more_buttons", page_listing_more_buttons)

else:

    if WAGTAIL_VERSION >= (2, 16, 0):
        hooks.register("register_page_header_buttons", page_listing_more_buttons)

    @hooks.register("register_page_listing_more_buttons")
    def register_page_listing_more_buttons(
        page, page_perms, is_parent=False, next_url=None
    ):
        for button in page_listing_more_buttons(page, page_perms, next_url):
            yield button


@hooks.register("register_snippet_listing_buttons")
def register_snippet_listing_buttons(snippet, user, next_url=None):
    model = type(snippet)

    if issubclass(model, TranslatableMixin) and user.has_perm(
        "wagtail_localize.submit_translation"
    ):
        # If there's at least one locale that we haven't translated into yet, show "Translate" button
        has_locale_to_translate_to = Locale.objects.exclude(
            id__in=snippet.get_translations(inclusive=True).values_list(
                "locale_id", flat=True
            )
        ).exists()

        if has_locale_to_translate_to:
            url = reverse(
                "wagtail_localize:submit_snippet_translation",
                args=[model._meta.app_label, model._meta.model_name, quote(snippet.pk)],
            )

            yield SnippetListingButton(
                _("Translate"),
                url,
                attrs={
                    "aria-label": _("Translate '%(title)s'") % {"title": str(snippet)}
                },
                priority=100,
            )

        # If the snippet is the source for translations, show "Sync translated snippets" button
        source = TranslationSource.objects.get_for_instance_or_none(snippet)
        if source is not None and source.translations.filter(enabled=True).exists():
            url = reverse("wagtail_localize:update_translations", args=[source.id])
            if next_url is not None:
                url += "?" + urlencode({"next": next_url})

            yield SnippetListingButton(
                _("Sync translated snippets"),
                url,
                attrs={
                    "aria-label": _("Sync translations of '%(title)s'")
                    % {"title": str(snippet)}
                },
                priority=106,
            )


@hooks.register("before_edit_page")
def before_edit_page(request, page):
    # If the page is an alias of a page in another locale, override the edit page so that we can show a "Translate this page" option
    if page.alias_of and page.alias_of.locale_id != page.locale_id:
        return edit_translation.edit_translatable_alias_page(request, page)

    # Check if the user has clicked the "Start Synced translation" menu item
    if request.method == "POST":
        if "localize-restart-translation" in request.POST:
            try:
                translation = Translation.objects.get(
                    source__object_id=page.translation_key,
                    target_locale_id=page.locale_id,
                    enabled=False,
                )
            except Translation.DoesNotExist:
                pass
            else:
                return edit_translation.restart_translation(request, translation, page)
        elif "localize-convert-to-alias" in request.POST:
            return redirect(
                reverse("wagtail_localize:convert_to_alias", args=[page.id])
            )

    # Overrides the edit page view if the page is the target of a translation
    try:
        translation = Translation.objects.get(
            source__object_id=page.translation_key,
            target_locale_id=page.locale_id,
            enabled=True,
        )
        return edit_translation.edit_translation(request, translation, page)

    except Translation.DoesNotExist:
        pass


class RestartTranslationPageActionMenuItem(PageActionMenuItem):
    label = gettext_lazy("Start Synced translation")
    name = "localize-restart-translation"
    icon_name = "undo"
    classname = "action-secondary"

    def is_shown(self, context):
        # Only show this menu item on the edit view where there was a previous translation record
        if context["view"] != "edit":
            return False

        return Translation.objects.filter(
            source__object_id=context["page"].translation_key,
            target_locale_id=context["page"].locale_id,
            enabled=False,
        ).exists()


@hooks.register("register_page_action_menu_item")
def register_restart_translation_page_action_menu_item():
    return RestartTranslationPageActionMenuItem(order=0)


class ConvertToAliasPageActionMenuItem(PageActionMenuItem):
    label = gettext_lazy("Convert to alias page")
    name = "localize-convert-to-alias"
    icon_name = "wagtail-localize-convert"
    classname = "action-secondary"

    def is_shown(self, context):
        # Only show this menu item on the edit view where there was a previous translation record
        if context["view"] != "edit":
            return False
        page = context["page"]
        try:
            return (
                page.alias_of_id is None
                and Page.objects.filter(
                    ~Q(pk=page.pk),
                    translation_key=page.translation_key,
                    locale_id=TranslationSource.objects.get(
                        object_id=page.translation_key,
                        specific_content_type=page.content_type_id,
                        translations__target_locale=page.locale_id,
                    ).locale_id,
                ).exists()
            )
        except TranslationSource.DoesNotExist:
            return False


@hooks.register("register_page_action_menu_item")
def register_convert_back_to_alias_page_action_menu_item():
    return ConvertToAliasPageActionMenuItem(order=0)


@hooks.register("before_edit_snippet")
def before_edit_snippet(request, instance):
    if isinstance(instance, TranslatableMixin):
        # Check if the user has clicked the "Start Synced translation" menu item
        if request.method == "POST" and "localize-restart-translation" in request.POST:
            try:
                translation = Translation.objects.get(
                    source__object_id=instance.translation_key,
                    target_locale_id=instance.locale_id,
                    enabled=False,
                )
            except Translation.DoesNotExist:
                pass
            else:
                return edit_translation.restart_translation(
                    request, translation, instance
                )

        # Overrides the edit snippet view if the snippet is translatable and the target of a translation
        try:
            translation = Translation.objects.get(
                source__object_id=instance.translation_key,
                target_locale_id=instance.locale_id,
                enabled=True,
            )
            return edit_translation.edit_translation(request, translation, instance)

        except Translation.DoesNotExist:
            pass


class RestartTranslationSnippetActionMenuItem(SnippetActionMenuItem):
    label = gettext_lazy("Start Synced translation")
    name = "localize-restart-translation"
    icon_name = "undo"
    classname = "action-secondary"

    def is_shown(self, context):
        # Only show this menu item on the edit view where there was a previous translation record
        if context["view"] != "edit":
            return False

        if not issubclass(context["model"], TranslatableMixin):
            return False

        return Translation.objects.filter(
            source__object_id=context["instance"].translation_key,
            target_locale_id=context["instance"].locale_id,
            enabled=False,
        ).exists()


@hooks.register("register_snippet_action_menu_item")
def register_restart_translation_snippet_action_menu_item(model):
    return RestartTranslationSnippetActionMenuItem(order=0)


class TranslationsReportMenuItem(MenuItem):
    def is_shown(self, request):
        return True


@hooks.register("register_reports_menu_item")
def register_wagtail_localize2_report_menu_item():
    return TranslationsReportMenuItem(
        _("Translations"),
        reverse("wagtail_localize:translations_report"),
        icon_name="site",
        order=9000,
    )


@hooks.register("register_log_actions")
def wagtail_localize_log_actions(actions):
    @actions.register_action("wagtail_localize.convert_to_alias")
    class ConvertToAliasActionFormatter(LogFormatter):
        label = gettext_lazy("Convert page to alias")

        def format_message(self, log_entry):
            try:
                return _(
                    "Converted page '%(title)s' to an alias of the translation source page '%(source_title)s'"
                ) % {
                    "title": log_entry.data["page"]["title"],
                    "source_title": log_entry.data["source"]["title"],
                }
            except KeyError:
                return _("Converted page to an alias of the translation source page")


@hooks.register("register_icons")
def register_icons(icons):
    return icons + [
        # icon id "wagtail-localize-convert" (which translates to `.icon-wagtail-localize-convert`)
        "wagtail_localize/icons/wagtail-localize-convert.svg",
        # icon id "wagtail-localize-language" (which translates to `.icon-wagtail-localize-language`)
        "wagtail_localize/icons/wagtail-localize-language.svg",
    ]
