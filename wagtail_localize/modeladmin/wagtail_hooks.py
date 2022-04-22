from django.urls import include, path
from wagtail.core import hooks

from .views import SubmitModelAdminTranslationView


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [
        path(
            "submit/<slug:app_label>/<slug:model_name>/<str:pk>/",
            SubmitModelAdminTranslationView.as_view(),
            name="submit_translation",
        ),
    ]
    return [
        path(
            "localize/modeladmin/",
            include(
                (urls, "wagtail_localize_modeladmin"),
                namespace="wagtail_localize_modeladmin",
            ),
        )
    ]
