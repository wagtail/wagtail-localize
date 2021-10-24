# Content Paths

Content paths are used by Wagtail Localize to reference a field within a page or snippet. They are needed for two purposes:

- They are generated whenever Wagtail Localize extracts segments from an object to provide an address for inserting the translations later on
- They are used in the `msgctxt` field in PO files to allow the same source string to be translated differently for different fields

This document describes how content paths are generated.

## Model fields

Model field content path's are the most simple, they just take the name of the field.

For example, with the given model:

```python
class Country(TranslatableMixin, models.Model):
    name = models.CharField(max_length=255)
```

The content path of the text extracted from the `name` field would be 'name'.

## Fields on translatable inline child objects

Format: `<child relation name>.<translation key of child object>.<field name>`

Inline child objects are the instances within an inline panel. Their models usually have a `ParentalKey` to a page. For example:

```python
class CountryPage(Page):
    content_panels = [
        InlinePanel("cities"),
    ]


class CountryPageCity(TranslatableMixin, Orderable):
    page = ParentalKey(CountryPage, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=255)
```

As all translatable inline child models must inherit from `TranslatableMixin`, each instance would have its own UUID in the `translation_key` field which we can use in the content path.

The content path of the text extracted from the `name` field would be `cities.76d048e6-2f04-4ff1-b7c6-f2630dc72b35.name` where `76d048e6-2f04-4ff1-b7c6-f2630dc72b35` is the value of the `translation_key` field on the inline child object itself (which it gets because it inherits from `TranslatableMixin`).

### Why not use the inline child's ID?

We need to use an identifier that can be shared with the translations as well. Translations of this page will have their own set of child objects so they will have different IDs as well. The `translation_key` field, however, keeps it's value across all translations so we can use this to find the correct translated child object to insert an updated translation into.

## StreamField blocks

Format: `<streamfield field name>.<block id>`

All StreamField blocks have a UUID that is shared across translations, so the translation of a streamfield block will have the same UUID as the source. This allows us to use it in the content path.

## StreamField StructBlock fields

Format: `<streamfield field name>.<block id>.<structblock field name>`

If the StreamField block is a `StructBlock`, we append the name of the field within the `StructBlock` to the end of the content path.

## What is not supported

### `ListBlock`

GitHub Issue: [#22](https://github.com/wagtail/wagtail-localize/issues/22)

It isn't possible to generate content paths to instances within a `ListBlock` as there is no stable identifier that we can use to reference each instance.

Content paths need to be stable across revisions. We can't use the index of instances within a `ListBlock` as these can be changed if a user re-orders the blocks and may cause translations to be inserted into the wrong blocks!

The recommended work around at the moment is to change all `ListBlock`s into nested `StreamBlock`s instead.

We should be able to solve this one when [Wagtail RFC 65](https://github.com/wagtail/rfcs/pull/65) is implemented, which adds UUIDs into `ListBlock`.
