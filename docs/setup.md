## Installation

Install with pip:

```shell
pip install wagtail-localize
```

## Settings modifications

Add `wagtail_localize` and any optional sub modules to `INSTALLED_APPS` in `settings/base.py`:

```python
INSTALLED_APPS = [
    ...
    "wagtail_localize",
    "wagtail_localize.admin.language_switch",
    "wagtail_localize.admin.regions",
    "wagtail_localize.admin.workflow",
    "wagtail_localize.translation",
    "wagtail_localize.translation_engines.google_translate",
]
```

Also remove the following from `INSTALLED_APPS`:

```
"wagtail.contrib.redirects",
```

Add the following to `MIDDLEWARE`:

```python
"django.middleware.locale.LocaleMiddleware",
```

and disable:

```python
"wagtail.contrib.redirects.middleware.RedirectMiddleware",
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
