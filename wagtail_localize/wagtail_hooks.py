from django.conf.urls import url, include
from django.contrib.auth.models import Permission

from wagtail.core import hooks


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [

    ]

    return [
        url(
            r"^localize/",
            include(
                (urls, "wagtail_localize"),
                namespace="wagtail_localize",
            ),
        )
    ]


@hooks.register('register_permissions')
def register_submit_translation_permission():
    return Permission.objects.filter(content_type__app_label='wagtail_localize', codename='submit_translation')
