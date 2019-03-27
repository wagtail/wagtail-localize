from django.conf.urls import include, url

from wagtail.core import hooks

from wagtail_i18n.plugins.workflow.action_modules import BaseActionModule

from .views import translate


class SubmitToGoogleTranslateActionModule(BaseActionModule):
    template_name = 'wagtail_i18n_google_translate/action_module.html'


@hooks.register('wagtail_i18n_workflow_register_action_modules')
def wagtail_i18n_workflow_register_action_modules():
    return [
        SubmitToGoogleTranslateActionModule,
    ]


@hooks.register('register_admin_urls')
def register_admin_urls():
    urls = [
        url('^translate/(\d+)/$', translate, name='translate'),
    ]

    return [
        url('^i18ngoogletranslate/', include((urls, 'wagtail_i18n_google_translate'), namespace='wagtail_i18n_google_translate')),
    ]
