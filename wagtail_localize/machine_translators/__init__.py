from django.conf import settings
from django.utils.module_loading import import_string


def get_machine_translator():
    config = getattr(settings, "WAGTAILLOCALIZE_MACHINE_TRANSLATOR", None)

    if config is None:
        return

    # Raises ImportError
    machine_translator_class = import_string(config["CLASS"])

    return machine_translator_class(config.get("OPTIONS", {}))
