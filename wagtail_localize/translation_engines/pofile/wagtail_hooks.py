from django.conf.urls import include, url

from wagtail.core import hooks

from wagtail_localize.admin.workflow.action_modules import BaseActionModule

from .views import download, upload


class DownloadUploadPOFileActionModule(BaseActionModule):
    template_name = "wagtail_localize_pofile/action_module.html"


@hooks.register("wagtail_localize_workflow_register_action_modules")
def wagtail_localize_workflow_register_action_modules():
    return [DownloadUploadPOFileActionModule]


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        url("^download/(\d+)/$", download, name="download"),
        url("^upload/(\d+)/$", upload, name="upload"),
    ]

    return [
        url(
            "^localize/engine/pofile/",
            include(
                (urls, "wagtail_localize_pofile"), namespace="wagtail_localize_pofile"
            ),
        )
    ]
