# Configuring translatable fields

By default, Wagtail Localize will decide for you which fields are translatable and which fields should just be synchronised.
This is decided by some simple rules described in the [Auto-generation of Translatable Fields](/concept/translatable-fields-autogen)
explanation.

This guide describes how to override this behaviour partially or completely. Firstly, a quick explanation of what this configuration
does.

## Types of translatable field

### Translatable

On text fields, this means that the content of the field will be extracted for translation by editors.

On foreign keys, this means that the referenced model is translatable, and when the translation is created or updated,
the field on the translation will be automatically linked to the translation of the object referenced by the source.

On StreamFields, this means that any translatable fields will be extracted for translatation, but some blocks may still
be synchronised.

On child relations (defined by ``ParentalKey``), this means that the child model is translatable, and itself contains
translatable fields that need to be extracted.

### Synchronised

For all fields, this means that the value will be copied across whenever the translation is updated.

Some synchronised fields can be overridden on translations, this currently depends on whether that field type is supported
by the translation editing interface.

### Neither / excluded

If a field is not defined as translatable or synchronised, they will not be updated in any way after the translation is first
created. This is generally only for internal non-editable fields such as ``id`` and page paths.

## Partially overriding Wagtail's translatable field auto-generation

By defining a ``override_translatable_fields`` attribute on the model, you can change whether a specific field should
be set as translatable or synchronised.

For example, by default the ``slug`` field on pages is translatable. If you would prefer not to translate this, you can
set it up as syncronised instead using the following snippet:

```python
from wagtail.core.models import Page

from wagtail_localize.fields import SynchronizedField


class BlogPage(Page):
    body = RichTextField()

    # Make the slug synchronised, but let Wagtail decide what to do with title/body
    override_translatable_fields = [
        SynchronizedField('slug'),
    ]
```

## Completely overriding Wagtail's translatable field auto-generation

To completely disable Wagtail's auto generation, you can set the ``translatable_fields`` attribute on the model.

```python
from wagtail.core.models import Page

from wagtail_localize.fields import TranslatableField, SynchronizedField


class BlogPage(Page):
    body = RichTextField()

    # Only translate title/body/slug, ignore all other fields
    translatable_fields = [
        TranslatableField('title'),
        TranslatableField('body'),
        SynchronizedField('slug'),
    ]
```
