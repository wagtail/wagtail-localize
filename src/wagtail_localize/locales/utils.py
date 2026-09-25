from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.models import get_translatable_models


if WAGTAIL_VERSION >= (8, 0):
    import swapper

    Page = swapper.load_model("wagtailcore", "Page")
else:
    from wagtail.models import Page


def get_locale_usage(locale):
    """
    Returns the number of pages and other objects that use a locale
    """
    num_pages = Page.objects.filter(locale=locale).exclude(depth=1).count()

    num_others = 0

    for model in get_translatable_models():
        if model is Page:
            continue

        num_others += model.objects.filter(locale=locale).count()

    return num_pages, num_others
