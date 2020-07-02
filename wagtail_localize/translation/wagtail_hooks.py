from django.contrib.auth.models import Permission
from django.conf.urls import url, include
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.admin.menu import MenuItem
from wagtail.core import hooks
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.models import TranslatablePageMixin

from .views.create_translation_request import create_translation_request
from .views.management import TranslationViewSet
from .views.translate import export_file, import_file, machine_translate, translation_form


@hooks.register("register_page_listing_more_buttons")
def page_listing_more_buttons(page, page_perms, is_parent=False, next_url=None):
    if isinstance(page, TranslatablePageMixin):
        yield wagtailadmin_widgets.Button(
            "Create translation request",
            reverse(
                "wagtail_localize_translation:create_translation_request", args=[page.id]
            ),
            priority=60,
        )


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        url(
            "^create_translation_request/(\d+)/$",
            create_translation_request,
            name="create_translation_request",
        ),
        url("^machine_translate/(\d+)/$", machine_translate, name="machine_translate"),
        url("^export_file/(\d+)/$", export_file, name="export_file"),
        url("^import_file/(\d+)/$", import_file, name="import_file"),
        url("^translation_form/(\d+)/$", translation_form, name="translation_form"),
    ]

    return [
        url(
            "^localize/translation/",
            include(
                (urls, "wagtail_localize_translation"),
                namespace="wagtail_localize_translation",
            ),
        )
    ]


@hooks.register("register_admin_viewset")
def register_viewset():
    return TranslationViewSet(
        "wagtail_localize_translation_management",
        url_prefix="localize/translation/translations",
    )


class TranslationsMenuItem(MenuItem):
    def is_shown(self, request):
        return True


@hooks.register("register_admin_menu_item")
def register_menu_item():
    return TranslationsMenuItem(
        _("Translations"),
        reverse("wagtail_localize_translation_management:list"),
        classnames="icon icon-site",
        order=500,
    )
