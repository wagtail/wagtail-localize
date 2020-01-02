from django.conf.urls import url, include
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from wagtail.admin.menu import MenuItem
from wagtail.core import hooks

from . import views


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        url("^$", views.dashboard, name="dashboard"),
        url("^force-sync/$", views.force_sync, name="force_sync"),
    ]

    return [
        url(
            "^localize/pontoon/",
            include(
                (urls, "wagtail_localize_pontoon"), namespace="wagtail_localize_pontoon"
            ),
        )
    ]


class PontoonMenuItem(MenuItem):
    def is_shown(self, request):
        return True


@hooks.register("register_settings_menu_item")
def register_menu_item():
    return PontoonMenuItem(
        _("Pontoon"),
        reverse("wagtail_localize_pontoon:dashboard"),
        classnames="icon icon-site",
        order=500,
    )
