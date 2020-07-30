from django.conf.urls import url, include

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
