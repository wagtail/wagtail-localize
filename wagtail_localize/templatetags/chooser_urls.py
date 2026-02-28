from contextlib import suppress

from django import template
from django.apps import apps
from django.urls import NoReverseMatch, reverse


register = template.Library()


@register.simple_tag
def wagtailmedia_is_installed():
    return apps.is_installed("wagtailmedia")


@register.simple_tag
def get_chooser_urls():
    urls = {
        "imageChooser": reverse("wagtailimages_chooser:choose"),
        "documentChooser": reverse("wagtaildocs_chooser:choose"),
        "pageChooser": reverse("wagtailadmin_choose_page"),
    }

    if wagtailmedia_is_installed():
        with suppress(NoReverseMatch):
            urls["mediaChooser"] = reverse("wagtailmedia:chooser")

    return urls
