from django.contrib.auth.models import Permission
from django.conf.urls import url, include
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.admin.menu import MenuItem
from wagtail.core import hooks
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.models import TranslatablePageMixin

from .models import TranslationRequest
from .views.create_translation_request import create_translation_request
from .views.management import TranslationRequestViewSet


@hooks.register("register_page_listing_more_buttons")
def page_listing_more_buttons(page, page_perms, is_parent=False):
    if isinstance(page, TranslatablePageMixin):
        yield wagtailadmin_widgets.Button(
            "Create translation request",
            reverse(
                "wagtail_localize_workflow:create_translation_request", args=[page.id]
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
        )
    ]

    return [
        url(
            "^localize/workflow/",
            include(
                (urls, "wagtail_localize_workflow"),
                namespace="wagtail_localize_workflow",
            ),
        )
    ]


@hooks.register("register_admin_viewset")
def register_viewset():
    return TranslationRequestViewSet(
        "wagtail_localize_workflow_management",
        url_prefix="localize/workflow/translations",
    )


class TranslationsMenuItem(MenuItem):
    def is_shown(self, request):
        return True


@hooks.register("register_admin_menu_item")
def register_menu_item():
    return TranslationsMenuItem(
        _("Translations"),
        reverse("wagtail_localize_workflow_management:list"),
        classnames="icon icon-site",
        order=500,
    )
