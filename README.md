# Wagtail localize

Supported versions:

Python: 3.7 and 3.8
Django: 2.2, 3.0 and 3.1
Wagtail: 2.11

## Installation and setup

Install with pip:

```shell
pip install wagtail-localize
```

### Settings modifications

Add `wagtail_localize` and `wagtail_localize.locales` to `INSTALLED_APPS` in `settings/base.py`:

```python
INSTALLED_APPS = [
    ...
    "wagtail_localize",
    "wagtail_localize.locales",  # Note: This replaces "wagtail.locales"
    ...
]
```

Add the following to `MIDDLEWARE`:

```python
"django.middleware.locale.LocaleMiddleware",
```

Ensure your settings file has:

```python
LANGUAGE_CODE = "en-gb"  # Or your preferred default language
USE_I18N = True
```

Add to following to your settings specifying any languages you would like to translate:

```python
LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
]
```

To enable DeepL as a machine translator, add the following to your settings:

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    'CLASS': 'wagtail_localize.machine_translators.deepl.DeepLTranslator',
    'OPTIONS': {
        'AUTH_KEY': '<Your DeepL key here>',
    }
}
```

### URL configuration

The following additions need to be made to `./yoursite/urls.py`

```python
from django.conf.urls.i18n import i18n_patterns
...

urlpatterns += i18n_patterns(
    url(r"^search/$", search_views.search, name="search"),
    url(r"", include(wagtail_urls)),
)
```

