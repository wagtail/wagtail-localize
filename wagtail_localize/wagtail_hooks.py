from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.contrib.auth.models import Permission
from django.urls import reverse, path, include
from django.utils.translation import gettext as _

from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.core import hooks
from wagtail.core.models import Locale, TranslatableMixin
from wagtail.snippets.widgets import SnippetListingButton

from .views import submit_translations


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path("submit/page/<int:page_id>/", submit_translations.SubmitPageTranslationView.as_view(), name="submit_page_translation"),
        path("submit/snippet/<slug:app_label>/<slug:model_name>/<str:pk>/", submit_translations.SubmitSnippetTranslationView.as_view(), name="submit_snippet_translation"),
    ]

    return [
        path(
            "localize/",
            include(
                (urls, "wagtail_localize"),
                namespace="wagtail_localize",
            ),
        )
    ]


@hooks.register('register_permissions')
def register_submit_translation_permission():
    return Permission.objects.filter(content_type__app_label='wagtail_localize', codename='submit_translation')


@hooks.register("register_page_listing_more_buttons")
def page_listing_more_buttons(page, page_perms, is_parent=False, next_url=None):
    if page_perms.user.has_perm('wagtail_localize.submit_translation') and not page.is_root():
        # If there's at least one locale that we haven't translated into yet, show "Translate this page" button
        has_locale_to_translate_to = Locale.objects.exclude(
            id__in=page.get_translations(inclusive=True).values_list('locale_id', flat=True)
        ).exists()

        if has_locale_to_translate_to:
            url = reverse("wagtail_localize:submit_page_translation", args=[page.id])
            if next_url is not None:
                url += '?' + urlencode({'next': next_url})

            yield wagtailadmin_widgets.Button(_("Translate this page"), url, priority=60)


@hooks.register('register_snippet_listing_buttons')
def register_snippet_listing_buttons(snippet, user, next_url=None):
    model = type(snippet)

    if issubclass(model, TranslatableMixin) and user.has_perm('wagtail_localize.submit_translation'):
        # If there's at least one locale that we haven't translated into yet, show "Translate" button
        has_locale_to_translate_to = Locale.objects.exclude(
            id__in=snippet.get_translations(inclusive=True).values_list('locale_id', flat=True)
        ).exists()

        if has_locale_to_translate_to:
            url = reverse('wagtail_localize:submit_snippet_translation', args=[model._meta.app_label, model._meta.model_name, quote(snippet.pk)])
            if next_url is not None:
                url += '?' + urlencode({'next': next_url})

            yield SnippetListingButton(
                _('Translate'),
                url,
                attrs={'aria-label': _("Translate '%(title)s'") % {'title': str(snippet)}},
                priority=100
            )
