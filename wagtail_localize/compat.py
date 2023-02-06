import os

from django.contrib.admin.utils import quote
from django.urls import reverse


if os.name == "nt":
    # Windows has a different strftime format for dates without leading 0
    # https://stackoverflow.com/questions/904928/python-strftime-date-without-leading-0
    DATE_FORMAT = "%#d %B %Y"
else:
    DATE_FORMAT = "%-d %B %Y"


def get_snippet_list_url(snippet):
    return reverse(
        f"wagtailsnippets_{snippet._meta.app_label}_{snippet._meta.model_name}:list"
    )


def get_snippet_edit_url(snippet):
    return reverse(
        f"wagtailsnippets_{snippet._meta.app_label}_{snippet._meta.model_name}:edit",
        args=[quote(snippet.pk)],
    )


def get_snippet_edit_url_from_args(app_label, model_name, pk):
    return reverse(f"wagtailsnippets_{app_label}_{model_name}:edit", args=[quote(pk)])


def get_snippet_delete_url(snippet):
    return reverse(
        f"wagtailsnippets_{snippet._meta.app_label}_{snippet._meta.model_name}:delete",
        args=[quote(snippet.pk)],
    )


def get_revision_model():
    return "wagtailcore.Revision"
