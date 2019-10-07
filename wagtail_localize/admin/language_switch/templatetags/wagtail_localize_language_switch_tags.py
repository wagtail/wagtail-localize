from django import template

from wagtail_localize.models import TranslatablePageMixin


register = template.Library()


@register.inclusion_tag(
    "wagtail_localize_language_switch/_language_switch.html", takes_context=True
)
def admin_language_switch(context):
    page = context["page"]
    is_translatable = True

    if isinstance(page, TranslatablePageMixin):
        language_count = page.get_translations().count()
    else:
        is_translatable = False
        language_count = 0

    return {
        "page": page,
        "is_translatable": is_translatable,
        "language_count": language_count,
    }
