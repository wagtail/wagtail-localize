from django import template
from django.urls import reverse, NoReverseMatch
from django.apps import apps

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
        try:
            urls["mediaChooser"] = reverse("wagtailmedia:chooser")
        except NoReverseMatch:
            pass

    return urls
