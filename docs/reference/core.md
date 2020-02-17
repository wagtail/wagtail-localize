# Core

The core app provides the basic models and utilities that are required by all `wagtail-localize` features.
It also provides some simple admin interface enhancements to make managing multiple trees easier.

## Models

The core models module is importable from `wagtail_localize.models`.

### Locale

`wagtail_localize.models.Locale`

This model stores "Locales" which could either be languages or language/region combinations (or a mix of the two).

This model is meant to be kept in sync with the value of the `LANGUAGES` setting in Django.
The `sync_languages` management command can be used to synchronise this model with the value of that setting.

#### Fields

 - `language_code` (string, unique) -
   The language or language/region code. For example, `en`, `en-GB`, `es`, `zh-Hans`

 - `is_active` (boolean, default `True`) -
   Set to `True` when the locale is created.
   If the language is removed from `LANGUAGES`, it will be changed to `False` instead of deleting the locale to maintain refrential integrity.

#### Methods

- `get_display_name()` -
  Returns the display name of the assoicated language defined in `LANGUAGES`.

- `@classmethod get_active()` -
  Returns the currently active locale.
  The active language may be set by Django's `LocaleMiddleware` or manually using `translation.activate()`.

- `get_all_pages()` -
  Returns a `QuerySet` of all pages that are in the locale.

### TranslatableMixin

`wagtail_localize.models.TranslatableMixin`

This model adds fields and methods to a model to make it translatable.
This version should be used on non-page models such as snippets, child objects and other models.
Pages should use `TranslatablePageMixin` instead, which has all the same methods but with some extra logic specific to pages.

#### Fields

 - `locale` (Foreign Key to `Locale`) -
   Links to the `Locale` representing the language that this page is written in.

 - `translation_key` (`UUID`) -
   An ID that is shared with all translations of an individual page. Only one instance may exist for a given translation key and locale.

 - `is_source_translation` (boolean) -
   This is set to `True` if it is the original version of the page and not a translation.
   This can be used by workflows that might want to prevent direct edits to translations, such as when translations are managed in an external system.

#### Methods

TODO

### TranslatablePageMixin

`wagtail_localize.models.TranslatablePageMixin`

This is a speicialised version of `TranslatableMixin` but for pages and contains all of it's fields and methods as well.
It adds one extra field and implements the logic for managing multiple language trees.

#### Fields

 - `placeholder_locale` (optional Foreign Key to `Locale`) -
   If this page is a placeholder, this links to the `Locale` that this instance was copied from.
   Placeholders are used to allow incremental translation by filling in all the gaps of untranslated content with copies from the most similar languages.

### TranslatablePageRoutingMixin

`wagtail_localize.models.TranslatablePageRoutingMixin`

Overrides page routing behaviour to allow routing into other languages to happen.

Normally Wagtail sites can have only one root page, this mixin can be applied to the site root's page type (usually the homepage type) to override and reroute requests that came from a foreign language browser.

### BootstrapTranslatableMixin

`wagtail_localize.models.BootstrapTranslatableMixin`

A version of `TranslatableMixin` without uniqueness constraints. Used to set initial `translation_key` on existing content before adding `TranslatableMixin` or `TranslatablePageMixin`.

## Utilities

The core utilities are importable from `wagtail_localize.utils`

### find_available_slug(parent_page, requested_slug)

This function finds a unique slug under the specified parent page based on the given `requested_slug`.

If the `requested_slug` is available, it is returned, otherwise a number is appended to it. The first number that is available is returned.

For example:

```python

>>> find_available_slug(page, "slug-that-isnt-used-yet")
"slug-that-isnt-used-yet"

>>> find_available_slug(page, "slug-that-is-already-used")
"slug-that-is-already-used-2"
```

### get_fallback_languages(language_code)

Returns a list of possible fallbacks for the given language code base on what is configured in `LANGUAGES`. The langauges are ordered by best-first.

For example:

```python
# settings.py

LANGUAGES = [
    ("en", "English"),
    ("en-GB", "English (UK)"),
    ("en-US", "English (USA)"),
    ("es", "Spanish"),
]
```

```python
>>> get_fallback_languages('en-GB')
['en', 'en-US']
