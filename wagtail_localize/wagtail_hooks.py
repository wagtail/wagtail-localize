from django.conf.urls import url, include
from django.templatetags.static import static
from django.utils.html import format_html_join

from wagtail.core import hooks

from . import admin_views


@hooks.register("insert_editor_js")
def insert_editor_js():
    js_files = ["wagtail_localize/js/page-editor.js"]
    return format_html_join(
        "\n",
        '<script src="{0}"></script>',
        ((static(filename),) for filename in js_files),
    )


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [url(r"^translations_list/(\d+)/$", admin_views.translations_list_modal, name="translations_list_modal")]

    return [
        url(
            r"^localize/",
            include(
                (urls, "wagtail_localize"),
                namespace="wagtail_localize",
            ),
        )
    ]
