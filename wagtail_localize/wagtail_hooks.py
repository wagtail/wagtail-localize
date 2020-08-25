from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.contrib.auth.models import Permission
from django.urls import reverse, path, include
from django.utils.translation import gettext as _
from django.views.i18n import JavaScriptCatalog

from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.core import hooks
from wagtail.core.models import Locale, TranslatableMixin
from wagtail.snippets.widgets import SnippetListingButton

from .models import Translation, TranslationSource
from .views import edit_translation, submit_translations, update_translations


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path('jsi18n/', JavaScriptCatalog.as_view(packages=['wagtail_localize']), name='javascript_catalog'),
        path("submit/page/<int:page_id>/", submit_translations.SubmitPageTranslationView.as_view(), name="submit_page_translation"),
        path("submit/snippet/<slug:app_label>/<slug:model_name>/<str:pk>/", submit_translations.SubmitSnippetTranslationView.as_view(), name="submit_snippet_translation"),
        path("update/<int:translation_source_id>/", update_translations.UpdateTranslationsView.as_view(), name="update_translations"),
        path("translate/<int:translation_id>/strings/<int:string_segment_id>/edit/", edit_translation.edit_string_translation, name="edit_string_translation"),
        path("translate/<int:translation_id>/pofile/download/", edit_translation.download_pofile, name="download_pofile"),
        path("translate/<int:translation_id>/pofile/upload/", edit_translation.upload_pofile, name="upload_pofile"),
        path("translate/<int:translation_id>/machine_translate/", edit_translation.machine_translate, name="machine_translate"),
        path("translate/<int:translation_id>/preview/", edit_translation.preview_translation, name="preview_translation"),
        path("translate/<int:translation_id>/preview/<str:mode>/", edit_translation.preview_translation, name="preview_translation"),
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

        # If the page is the source for translations, show "Update translations" button
        source = TranslationSource.objects.get_for_instance_or_none(page)
        if source is not None:
            url = reverse("wagtail_localize:update_translations", args=[source.id])
            if next_url is not None:
                url += '?' + urlencode({'next': next_url})

            yield wagtailadmin_widgets.Button(_("Update translations"), url, priority=65)


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

        # If the snippet is the source for translations, show "Update translations" button
        source = TranslationSource.objects.get_for_instance_or_none(snippet)
        if source is not None:
            url = reverse('wagtail_localize:update_translations', args=[source.id])
            if next_url is not None:
                url += '?' + urlencode({'next': next_url})

            yield SnippetListingButton(
                _('Update translations'),
                url,
                attrs={'aria-label': _("Update translations for '%(title)s'") % {'title': str(snippet)}},
                priority=106
            )


@hooks.register("before_edit_page")
def before_edit_page(request, page):
    # Overrides the edit page view if the page is the target of a translation
    try:
        translation = Translation.objects.get(source__object_id=page.translation_key, target_locale_id=page.locale_id, enabled=True)
        return edit_translation.edit_translation(request, translation, page)

    except Translation.DoesNotExist:
        pass


@hooks.register("before_edit_snippet")
def before_edit_snippet(request, instance):
    # Overrides the edit snippet view if the snippet is translatable and the target of a translation
    if isinstance(instance, TranslatableMixin):
        try:
            translation = Translation.objects.get(source__object_id=instance.translation_key, target_locale_id=instance.locale_id, enabled=True)
            return edit_translation.edit_translation(request, translation, instance)

        except Translation.DoesNotExist:
            pass
