from django import template


register = template.Library()


@register.inclusion_tag(
    "wagtail_localize/admin/_language_switch.html", takes_context=True
)
def admin_language_switch(context):
    page = context["page"]

    return {
        "page": page,
        "is_translatable": True,  # TODO Remove
        "language_count": page.get_translations().count(),
    }
