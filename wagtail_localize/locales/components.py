LOCALE_COMPONENTS = []


def get_locale_components():
    return LOCALE_COMPONENTS


def register_locale_component(*, required=False):
    def _wrapper(model):
        if model not in LOCALE_COMPONENTS:
            LOCALE_COMPONENTS.append({
                'required': required,
                'model': model,
                'slug': model._meta.db_table,
            })
            LOCALE_COMPONENTS.sort(key=lambda x: x['model']._meta.verbose_name)

        return model

    return _wrapper
