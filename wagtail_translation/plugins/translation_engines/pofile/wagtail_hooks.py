from django.conf.urls import include, url

from wagtail.core import hooks

from wagtail_translation.plugins.workflow.action_modules import BaseActionModule

from .views import download, upload


class DownloadUploadPOFileActionModule(BaseActionModule):
    template_name = 'wagtail_translation_pofile/action_module.html'


@hooks.register('wagtail_translation_workflow_register_action_modules')
def wagtail_translation_workflow_register_action_modules():
    return [
        DownloadUploadPOFileActionModule,
    ]


@hooks.register('register_admin_urls')
def register_admin_urls():
    urls = [
        url('^download/(\d+)/$', download, name='download'),
        url('^upload/(\d+)/$', upload, name='upload'),
    ]

    return [
        url('^translation/pofile/', include((urls, 'wagtail_translation_pofile'), namespace='wagtail_translation_pofile')),
    ]
