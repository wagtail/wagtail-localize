# Migrate from wagtail-modeltranslation


### Remove wagtail-modeltranslation


The package wagtail-modeltranslation, when installed and used, will add a new column in your database for every field
you have.

So if you have:
```
class MyPage(Page):
    custom_field = models.CharField(...)
```

It will generate `custom_field_en`, `custom_field_de`, `custom_field_fr`, and so on for every field in your page.

We need to remove the package and then remove the fields to clear out the database.

!!! note "Careful with production data"

    Make sure you run these steps in a testing environment first. Once the fields (above) are deleted from your
    database, the translations will be lost forever.


### Remove the packages from your INSTALLED_APPS

Find your ``INSTALLED_APPS`` and delete the following lines (if they are present):
```python
'wagtail_modeltranslation',
'wagtail_modeltranslation.makemigrations',
'wagtail_modeltranslation.migrate',
```

### Remove translation options

If you have any ``TranslationOptions`` used in any of your files, delete those classes too. They often look something
like this:

```python
from modeltranslation.translator import TranslationOptions
from modeltranslation.decorators import register

@register(MyWagtailPage)
class MyWagtailPageTR(TranslationOptions):
    fields = ('title', 'body',)
```

Deleting these classes will prevent Wagtail from trying to translate your content.

!!! note "A common practice..."

    A common practice with wagtail-modeltranslation is to use a ``translation.py`` file. If you only have translation
    classes in this file, you can delete the entire file.


### Make migrations and apply them

At this point your wagtail-modeltranslation code should be removed from your code base. The last step is to create
new migration files, and apply them to your database.

```bash
python manage.py makemigrations
python manage.py migrate
```

!!! note "Don't forget to update your requirement files"

    Make sure you update your requirment files, Pipfiles, and other source files so you aren't accidentally
    installing wagtail-modeltranslation again.


### You're ready to install wagtail-localize

Now that you have a non-localised version of Wagtail running, you are ready to install `wagtail-localize`.

See [Step 2. Configure Wagtail Localize](../../tutorial/2-configure-wagtail-localize.md) to get started installing
wagtail-localize.
