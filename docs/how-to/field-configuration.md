# Configuring translatable fields

!!! attention

    It is not currently possible to configure `StructBlock` translatable fields. See [Issue #307](https://github.com/wagtail/wagtail-localize/issues/307) for more details.

By default, Wagtail Localize will decide for you which fields are translatable and which fields should just be synchronised.
This is decided by some simple rules described in the [Auto-generation of Translatable Fields](/concept/translatable-fields-autogen)
explanation.

This guide describes how to override this behaviour partially or completely. Firstly, a quick explanation of what this configuration
does.

## Types of translatable fields

### Translatable

On text fields, this means that the content of the field will be extracted for translation by editors.

On foreign keys, this means that the referenced model is translatable, and when the translation is created or updated,
the field on the translation will be automatically linked to the translation of the object referenced by the source.

On StreamFields, this means that any translatable fields will be extracted for translatation, but some blocks may still
be synchronised.

On child relations (defined by `ParentalKey`), this means that the child model is translatable, and itself contains
translatable fields that need to be extracted.

### Synchronised

This means that the value of the field will be copied to the translation whenever the translation is updated.

Depending on the field type, synchronised fields can be overridden in translations. This means that the field will
be editable on individual translations, but this is optional. If the field is edited on a translation, it will no
longer receive updates from the source page until an editor clicks the "Revert to source version" button.

The overridability of a field can be explicitly disabled by a developer.

### Neither / excluded

If a field is not defined as translatable or synchronised, they will not be updated in any way after the translation is first
created. This is generally only for internal non-editable fields such as `id` and page paths.

## Partially overriding Wagtail's translatable field auto-generation

By defining a `override_translatable_fields` attribute on the model, you can change whether a specific field should
be set as translatable or synchronised.

For example, by default the `slug` field on pages is translatable. If you would prefer not to translate this, you can
set it up as syncronised instead using the following snippet:

```python
from wagtail.models import Page

from wagtail_localize.fields import SynchronizedField


class BlogPage(Page):
    body = RichTextField()

    # Make the slug synchronised, but let Wagtail decide what to do with title/body
    override_translatable_fields = [
        SynchronizedField("slug"),
    ]
```

## Removing the ability to override a `SynchronizedField`

Wagtail will decide if a field can be overridden depending on if its type.
You can tell Wagtail to not allow the field to be overridden by passing the keyword argument `overridable=False`.
For example:

```python
from wagtail.models import Page

from wagtail_localize.fields import SynchronizedField


class BlogPage(Page):
    body = RichTextField()

    # Make the slug synchronised, but don't allow it to be overridden on translations
    override_translatable_fields = [
        SynchronizedField("slug", overridable=False),
    ]
```

## Completely overriding Wagtail's translatable field auto-generation

To completely disable Wagtail's auto generation, you can set the `translatable_fields` attribute on the model.

```python
from wagtail.models import Page

from wagtail_localize.fields import TranslatableField, SynchronizedField


class BlogPage(Page):
    body = RichTextField()

    # Only translate title/body/slug, ignore all other fields
    translatable_fields = [
        TranslatableField("title"),
        TranslatableField("body"),
        SynchronizedField("slug"),
    ]
```
