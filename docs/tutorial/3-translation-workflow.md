# Translation workflow

Now we need to add an admin interface to allow translators to create and manage translations.

This functionality is provided by Wagtail localize in a set of optional add-ons which add various features to the Wagtail admin. In this tutorial, we will enable the “workflow” and “language_switch” modules.

## Installing the built-in workflow modules

Add the following into `INSTALLED_APPS` just below where you added `'``wagtail_localize``'``,` earlier:


    INSTALLED_APPS = [
        'home',
        'search',

        'wagtail_localize',
        'wagtail_localize.admin.language_switch',
        'wagtail_localize.admin.workflow',

        'wagtail.contrib.forms',
        ...
    ]

Now run `python manage.py migrate`


- `wagtail_localize.admin.language_switch` adds a language switcher to the page editor, allowing editors to easily switch between languages of a particular page
- `wagtail_localize.admin.workflow`


## A quick tour of the built-in workflow module



## Can I build my own?

Yes, you can. The whole purpose of making the workflow into an optional add-on is so that you can build something completely custom if you need to.



