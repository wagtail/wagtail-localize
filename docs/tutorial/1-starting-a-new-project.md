# Starting a new project

Welcome to the getting started tutorial! In this tutorial we will make a very simple blog that supports English and French.

## Starting a new Wagtail project

Install Wagtail (if you haven’t already) and start a new project using `wagtail start`


    # in a Python 3 virtual environment
    pip install wagtail
    wagtail start mysite
    cd mysite
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

For more details, see the [Wagtail install guide](https://docs.wagtail.io/en/stable/getting_started/tutorial.html?_ga=2.194093614.2067415752.1571405236-1644154380.1556183245)


- TODO windows instructions


## Installing Wagtail Localize

You can install the `wagtail-localize` package with pip using the following command:


    pip install wagtail-localize

Now we need to configure it TODO

In `mysite/settings/base.py`, add `wagtail_localize` into `INSTALLED_APPS` above the Wagtail apps:


    INSTALLED_APPS = [
        'home',
        'search',

        'wagtail_localize',

        'wagtail.contrib.forms',
        ...
    ]

In the same file make sure `LANGUAGE_CODE` is set to `'en-us'`, this would be our blog’s default language.

Also, set Our blog will only support US English and French, so let’s set `LANGUAGES` as well:


    LANGUAGES = [
        ('en-us', "English (United States)"),
        ('fr', "French"),
    ]

Now run the `migrate` management command to create the database tables and then run `sync_languages` which copies the value of `LANGUAGES` into the database:


    python manage.py migrate
    python manage.py sync_languages

If you decide to change the values of `LANGUAGE_CODE` or `LANGUAGES`, you must run the `sync_languages` command again to update the database.

We’re all set! In the next part of this tutorial we will add some translatable page models.
