from django.conf.urls import include, url

from wagtail.core import hooks

from wagtail_i18n.plugins.workflow.action_modules import BaseActionModule

from .views import download, upload


class DownloadUploadPOFileActionModule(BaseActionModule):
    template_name = 'wagtail_i18n_pofile/action_module.html'


@hooks.register('wagtail_i18n_workflow_register_action_modules')
def wagtail_i18n_workflow_register_action_modules():
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
        url('^i18npofile/', include((urls, 'wagtail_i18n_pofile'), namespace='wagtail_i18n_pofile')),
    ]
