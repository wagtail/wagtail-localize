# 2. Configure Wagtail Localize

In this section, you will enable internationalisation and configure Wagtail Localize in the site you created earlier.

## Settings

Open ``tutorial/settings/base.py`` in your favourite text editor.

### Add Wagtail Localize to ``INSTALLED_APPS``

Find the ``INSTALLED_APPS`` setting, and insert ``'wagtail_localize'`` and ``'wagtail_localize.locales'`` in between ``'search`` and ``'wagtail.contrib.forms'``:

``` python
INSTALLED_APPS = [
    'home',
    'search',

    # Insert these here
    'wagtail_localize',
    'wagtail_localize.locales',

    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    # ...
]
```

Note that the ``wagtail_localize.locales`` module is a temporary replacement for Wagtail's builtin ``wagtail.locales`` module and it will be removed in a later release.

### Enable Wagtail's internationalisation

Find the "Internationalisation" section, and add the ``WAGTAIL_I18N_ENABLED`` setting:

``` python
USE_I18N = True

USE_L10N = True

# Add this
WAGTAIL_I18N_ENABLED = True

USE_TZ = True
```

### Configure content languages

In the "Internationalisation" section, set the ``LANGUAGES`` and ``WAGTAIL_CONTENT_LANGUAGES`` settings to English and
French:

``` python
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ('en', "English"),
    ('fr', "French"),
]
```

This will allow content to be authored in either English or French (configured by ``WAGTAIL_CONTENT_LANGUAGES``) and
also use those same languages on the site frontend (configured by ``LANGUAGES``). It's possible in Wagtail Localize
to make languages share Wagtail content. One case where this is useful is for supporting regions like ``en-gb`` and
``en-us`` where you might want them to use the same content but differ on just date formatting and currency.

### Enable ``LocaleMiddleware``

Django's ``LocaleMiddleware`` detects a user's browser language and forwards them to the most approapriate language
version of the website.

To enable it, insert  ``'django.middleware.locale.LocaleMiddleware'`` into the middleware setting
above ``RedirectMiddleware``:

``` python
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Insert this here
    'django.middleware.locale.LocaleMiddleware',

    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
]
```

## URLs

We need to tell Django (the web framework that Wagtail is built on) which URL paths are translatable. For these
patterns, Django will prefix them with the language code. For example, if we tell Django that the search view is
translatable, the URL will change from ``/search/`` to ``/en/search/`` for English and ``/fr/search/`` for French.

To configure this, open ``tutorial/urls.py`` in your favourite text editor. You'll notice in there that there are two
groups of URL patterns with an ``if settings.DEBUG:`` block in the middle. It's done this way because the
``wagtail_urls`` entry must always be last.

To tell Django to prefix ``wagtail_urls`` and ``/search`` with a language code, wrap these patterns with
[``i18n_patterns``](https://docs.djangoproject.com/en/3.1/topics/i18n/translation/#django.conf.urls.i18n.i18n_patterns).
You can do this by ``'search/'`` path to the top of the second group of URL patterns and then replace the
square brackets around the second group with ``i18n_patterns()``:

``` python
from django.conf.urls.i18n import i18n_patterns


# These paths are translatable so will be given a language prefix (eg, '/en', '/fr')
urlpatterns = urlpatterns + i18n_patterns(
    path('search/', search_views.search, name='search'),

    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),

    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
)
```

With the ``'search/'`` path removed, the first group should now look like:

``` python
# These paths are non-translatable so will not be given a language prefix
urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
]
```

## Migrate the database

Run the migrate command again to set up the tables for Wagtail Localize in the database you created earlier:

``` shell
python manage.py migrate
```

## Check the site

Go back to ``http://localhost:8000``. If your browser is configured for English or any other language except French,
you should be redirected to ``http://localhost:8000/en/``.
If your browser is configured in French, you should be redirected to ``http://localhost:8000/fr/``.

In either case, you can view the site in ``/en/`` or ``/fr/``, but there are no differences yet, we will get to that in
the following sections!

If this is all working as described, that means ``i18n_patterns`` and ``LocaleMiddleware`` are both working!

## Check the admin

Now go back into the Wagtail admin interface. When you open the "Pages" menu, you shoud see that that the "Home" page
has been labelled as "English". If you see that, then Wagtail's internationalisation is working!

![Wagtail explorer menu with internationalisation enabled](/_static/tutorial/wagtail-explorer-with-i18n.png)

## Create the "French" locale

Wagtail Localize links all content to ``Locale`` objects in the database. This allows the language codes to be updated
easily and also allows custom components (such as currencies, flags, etc) to be associated with them in the database.

Wagtail Localize sets up only one ``Locale`` to begin with, which is the one the corresponds to the ``LANGUAGE_CODE``
setting. In this tutorial, we left ``LANGUAGE_CODE`` set to ``en-gb`` so the initial ``Locale`` would've been created
for "English" but not "French".

To set up a locale object, go to "Settings" => "Locales" in the admin interface, and click "Add a new locale". "French"
should be automatically selected as it is the only available option.

Set the "Sync from" field to "English". This keeps the "French" language tree in sync with any existing and new
English content as it's authored.

![Setting up the French locale](/_static/tutorial/wagtail-add-french-locale.png)

After you've pressed "Save", you should now see two "Home" pages in the page explorer:

![Wagtail explorer menu with English and French homepages](/_static/tutorial/wagtail-explorer-with-english-and-french.png)
