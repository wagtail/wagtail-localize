# Translation workflow

Now we need to add an admin interface to allow translators to create and manage translations.

This functionality is provided by Wagtail Localize in a set of optional add-ons which add various features to the Wagtail admin. In this tutorial, we will enable the “workflow” and “language_switch” modules.

## Installing the built-in workflow modules

Add the following into `INSTALLED_APPS` just below where you added `'``wagtail_localize``'``,` earlier:


    INSTALLED_APPS = [
        'home',
        'search',

        'wagtail_localize',
        'wagtail_localize.translation',
        'wagtail_localize.admin.language_switch',
        'wagtail_localize.admin.workflow',

        'wagtail.contrib.forms',
        ...
    ]

Now run `python manage.py migrate`


- `wagtail_localize.admin.language_switch` adds a language switcher to the page editor, allowing editors to easily switch between languages of a particular page
- `wagtail_localize.admin.workflow` adds the ability to submit pages for translation, and manage the resulting translation requests


## A quick tour of the built-in workflow module

Navigate to one of your newly created blog pages in the explorer. Select the `More` button, next to `Add child page`, then `Create translation request`. 

You'll be offered a choice of locales to translate to - in this case, `Default/French` is the only option. Check it, and submit the request.

On the menu sidebar, select the new menu item: `Translations`

You'll see a list of translation requests. Notice that your request actually contains two pages: your `HomePage` instance and the `BlogPage` instance you created it for.
This is because a page cannot be translated without its parent having been translated, as translated pages are stored in mirrored page trees.

Select the request, and you'll see a set of details. Currently, as we haven't got any translation backends configured, there's only one action we can take: to copy the pages 
from the source language to the destination. Choose this now.

In the explorer, you'll now see a parallel page tree for the new language - currently in draft.

## Language switching

Now we've translated a page, we can use the language switcher. Edit your translated `BlogPage`, and you'll see a new item in the top right of the screen: below the page lock and status
information, a `Translations` button. Click it, and you should see options to edit or preview the page's other translations.

## Adding a translation backend

Of course, normally you'd want to do more than copy pages from the source site when you make a translation request. You might want to submit the content to an external service.
This is accomplished by adding a translation backend - either one of the built-in options, or writing your own. 

For simplicity, we'll add the Google Translate backend as an example.
