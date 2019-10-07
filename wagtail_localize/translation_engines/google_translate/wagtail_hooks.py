from django.conf.urls import include, url

from wagtail.core import hooks

from wagtail_localize.admin.workflow.action_modules import BaseActionModule

from .views import language_code, translate


class SubmitToGoogleTranslateActionModule(BaseActionModule):
    template_name = "wagtail_localize_google_translate/action_module.html"

    def is_shown(self):
        # Hide if the language is not different between the locales
        source_lang = language_code(
            self.translation_request.source_locale.language.code
        )
        target_lang = language_code(
            self.translation_request.target_locale.language.code
        )

        return source_lang != target_lang


@hooks.register("wagtail_localize_workflow_register_action_modules")
def wagtail_localize_workflow_register_action_modules():
    return [SubmitToGoogleTranslateActionModule]


@hooks.register("register_admin_urls")
def register_admin_urls():
    urls = [url("^translate/(\d+)/$", translate, name="translate")]

    return [
        url(
            "^localize/engine/googletranslate/",
            include(
                (urls, "wagtail_localize_google_translate"),
                namespace="wagtail_localize_google_translate",
            ),
        )
    ]
