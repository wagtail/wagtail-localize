from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from wagtail.admin.menu import MenuItem
from wagtail.core import hooks
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.models import Region
from .views import RegionViewSet


@hooks.register("register_admin_viewset")
def register_viewset():
    return RegionViewSet(
        "wagtail_localize_regions_admin", url_prefix="localize/regions"
    )


class RegionsMenuItem(MenuItem):
    def is_shown(self, request):
        return ModelPermissionPolicy(Region).user_has_any_permission(
            request.user, ["add", "change", "delete"]
        )


@hooks.register("register_settings_menu_item")
def register_sites_menu_item():
    return RegionsMenuItem(
        _("Regions"),
        reverse("wagtail_localize_regions_admin:index"),
        classnames="icon icon-site",
        order=602,
    )


@hooks.register("register_permissions")
def register_permissions():
    return Permission.objects.filter(
        content_type__app_label="wagtail_localize_regions_admin",
        codename__in=["add_region", "change_region", "delete_region"],
    )
