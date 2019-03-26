from django.conf.urls import url, include
from django.urls import reverse

from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.contrib.modeladmin.options import ModelAdmin, modeladmin_register
from wagtail.core import hooks

from wagtail_i18n.models import TranslatablePageMixin

from .models import TranslationRequest
from .views import create_translation_request


@modeladmin_register
class TranslationRequestModelAdmin(ModelAdmin):
    model = TranslationRequest
    menu_label = 'Translations'


@hooks.register('register_page_listing_more_buttons')
def page_listing_more_buttons(page, page_perms, is_parent=False):
    if isinstance(page, TranslatablePageMixin):
        yield wagtailadmin_widgets.Button(
            'Create translation request',
            reverse('wagtail_i18n_workflow:create_translation_request', args=[page.id]),
            priority=60
        )


@hooks.register('register_admin_urls')
def register_admin_urls():
    urls = [
        url('^create_translation_request/(\d+)/$', create_translation_request, name='create_translation_request'),
    ]

    return [
        url('^i18nworkflow/', include(urls, namespace='wagtail_i18n_workflow')),
    ]
