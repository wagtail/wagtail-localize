from wagtail.admin.forms.models import WagtailAdminModelForm


LOCALE_COMPONENTS = []


def get_locale_components():
    return LOCALE_COMPONENTS


def register_locale_component(*, heading, help_text=None, required=False):
    def _wrapper(model):
        if model not in LOCALE_COMPONENTS:
            LOCALE_COMPONENTS.append(
                {
                    "heading": heading,
                    "help_text": help_text,
                    "required": required,
                    "model": model,
                    "slug": model._meta.db_table,
                }
            )
            LOCALE_COMPONENTS.sort(key=lambda x: x["model"]._meta.verbose_name)

        return model

    return _wrapper


class LocaleComponentModelForm(WagtailAdminModelForm):
    def validate_with_locale(self, locale):
        """
        Validates the locale component against the given locale.
        """
        pass
