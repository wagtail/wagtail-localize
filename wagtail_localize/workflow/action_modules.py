import functools

from django.template.loader import render_to_string

from wagtail.core import hooks

from wagtail_localize.translation.machine_translators import get_machine_translator


class BaseActionModule:
    template_name = None

    def __init__(self, request, translation_request):
        self.request = request
        self.translation_request = translation_request

    def is_shown(self):
        return True

    def render(self):
        context = {"translation_request": self.translation_request}

        return render_to_string(self.template_name, context, request=self.request)


class CopyPagesActionModule(BaseActionModule):
    template_name = "wagtail_localize_workflow/action_modules/copy_pages.html"


class MachineTranslatorActionModule(BaseActionModule):
    template_name = "wagtail_localize_workflow/action_modules/machine_translator.html"

    def is_shown(self):
        machine_translator = get_machine_translator()
        return machine_translator.can_translate(
            self.translation_request.source_locale,
            self.translation_request.target_locale,
        )


@functools.lru_cache()
def get_action_modules():
    action_modules = [CopyPagesActionModule]

    machine_translator = get_machine_translator()
    if machine_translator is not None:
        action_modules.append(MachineTranslatorActionModule)

    for fn in hooks.get_hooks("wagtail_localize_workflow_register_action_modules"):
        new_action_modules = fn()
        if new_action_modules:
            action_modules.extend(new_action_modules)

    return action_modules
