# Wagtail localize


## Installation and setup

Install with pip:

```shell
pip install wagtail-localize
```

### Settings modifications

Add `wagtail_localize` and any optional sub modules to `INSTALLED_APPS` in `settings/base.py`:

```python
INSTALLED_APPS = [
    ...
    "wagtail_localize",
    "wagtail_localize.admin.language_switch",
    "wagtail_localize.admin.regions",
    "wagtail_localize.admin.workflow",
    "wagtail_localize.translation_memory",
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

## Enabling Wagtail-localize within a new site

Wagtail-localize provides classes wich page models should extend if they are to be translatable. This will be different if you are enabling translation on an existing site with pages, or a new site.

#### TranslatablePageRoutingMixin

Returns the translation of the page that should be used to route the specified request.

#### TranslatableMixin

The base class for providing attributes needed to store translation mapping values:

- `translation_key` - A `UUID` that is shared between all translations of the same object/page
- `locale` - A foreign key to the `wagtail_localize.Locale` table which could represent a language or language/region
- `is_source_translation` - A boolean field that is `True` if this object is the translation source for objects with the same `translation_key`

This adds the following methods to the model:

 - `get_translations(inclusive=False)` - Returns a `QuerySet` of translations of this object. This object will be excluded from that `QuerySet` unless `inclusive` is set to `True`
 - `get_translation(locale)` - Returns the translated version of the object in that target locale. Raises `Model.DoesNotExist` if the object hasn't been translated into the that target locale
  - `get_translation_or_none(locale)` - Similar to `get_translation(locale)` except it returns `None` if the object hasn't been translated into the that target locale
 - `has_translation(locale)` - Returns `True` if the object has been translated into the target locale
 - `copy_for_translation(locale)` - Makes a copy of the object with the `locale` field of the new object set to the target locale

#### TranslatablePageMixin

A specialised version of `TranslatableMixin` to be used on page models. It has the following differences:

- The `copy_for_translation` method will create the new page underneath the translation of the parent page (for example, if a page in the English "News" section is copied for translation into German, the new page will be automatically created under the "Nachrichten" section in the German site tree)

- The `copy` method has been overridden to change the `translation_key` field. This method is called from the regular page copy action in the admin, it effectively creates a new page so the `translation_key` needs to be given a new value.

#### BootstrapTranslatableMixin

A version of `TranslatableMixin`/`TranslatablePageMixin` without uniqueness constraints. This is to make it easy to transition existing models to being translatable. This is only used for generating the correct migrations in order to set the `translation_key` field uniquely for existing content.

### 1. Enabling on a new site

The homepage should extend both `TranslatablePageMixin` and `TranslatablePageRoutingMixin`

```python
from wagtail_localize.models import TranslatablePageMixin, TranslatablePageRoutingMixin
...

class HomePage(TranslatablePageRoutingMixin, TranslatablePageMixin, Page):
```

Then each page model that requires translation should extend TranslatablePageMixin:

```
from wagtail_localize.models import TranslatablePageMixin
...

class ArticlePage(TranslatablePageMixin, SocialFields, ListingFields, Page):
```

### 2. Enabling on an existing site with page data

The process is as follows:

- Add `BootstrapTranslatableMixin` to your page models
- Run `django-admin makemigrations`
- Create a data migration for each app, then use the BootstrapTranslatableModel operation in
`wagtail_localize.bootstrap` on each model in that app
- Change `BootstrapTranslatableMixin` to `TranslatableMixin` (or `TranslatablePageMixin`, if it's a page model)
- Run `django-admin makemigrations` again


### Synchronising languages

`wagtail_localize` stores the list of available langauges in the database. To populate this to have the same values as is in the `LANGUAGES` DJango setting, you must run the following command:

```shell
python manage.py sync_languages
```

## TODO

### Optional modules

description of submodules
'wagtail_localize.admin.regions',
'wagtail_localize.admin.workflow',
'wagtail_localize.translation_memory',
'wagtail_localize.translation_engines.google_translate',

### Translating snippets
