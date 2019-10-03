# Wagtail localize


## Installation and setup

Install with pip:

```
pip install wagtail-localize
```

### Settings modifications

Add the wagtail_localize and any optional sub modules to INSTALLED_APPS in settings/base.py:

```
INSTALLED_APPS = [
    ...
    'wagtail_localize',
    'wagtail_localize.admin.language_switch',
    'wagtail_localize.admin.regions',
    'wagtail_localize.admin.workflow',
    'wagtail_localize.translation_memory',
    'wagtail_localize.translation_engines.google_translate',
]
```

Also Remove the following from INSTALLED_APPS:

```
"wagtail.contrib.redirects",
```

Add the following to MIDDLEWARE:

```
'django.middleware.locale.LocaleMiddleware',
```

and disable:

```
"wagtail.contrib.redirects.middleware.RedirectMiddleware",
```

Ensure your settings file has:

```
LANGUAGE_CODE = "en-gb"  # Or you're prefered default language
USE_I18N = True
```

Add to following to your settings specifying any languages you would like to translate:

```
WAGTAIL_SITE_MODEL = 'wagtail_localize_sites.Site'

LANGUAGES = [
    ('en', "English"),
    ('fr', "French"),
]
```



### URL configuration

The following additions need to be made to `./yoursite/urls.py`

```
from django.conf.urls.i18n import i18n_patterns
...

urlpatterns += i18n_patterns(
    url(r'^search/$', search_views.search, name='search'),
    url(r'', include(wagtail_urls)),
)
```

## Enabling Wagtail-localize within a new site

Wagtail-localize provides classes wich page models should extend if they are to be translatable. This will be different if you are enabling translation on an existing site with pages, or a new site.

#### TranslatablePageRoutingMixin
Returns the translation of the page that should be used to route the specified request.


#### TranslatableMixin
The base class for providing attributes needed to store translation mapping values:
- translation_key
- locale

#### TranslatabelPageMixin
Extends TranslatableMixin to provide a 'copy for translation' method

#### BootstrapTranslatablePageMixin
A version of TranslatableMixin without uniqueness constraints.
This is to make it easy to transition existing models to being translatable.

### 1. Enabling on a new site

The homepage should extend both TranslatabelPageMixin and TranslatablePageRoutingMixin

```
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
- Add BootstrapTranslatableMixin to your page models
- Run makemigrations
- Create a data migration for each app, then use the BootstrapTranslatableModel operation in
wagtail_localize.bootstrap on each model in that app
- Change BootstrapTranslatableMixin to TranslatableMixin (or TranslatablePageMixin, if it's a page model)
- Run makemigrations again
- Migrate!


After completing setup via one of the above options, the following command needs to be run.

```
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