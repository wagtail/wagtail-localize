# Configuring translatable fields

By default, Wagtail Localize will decide for you which fields are translatable and which fields should just be synchronised.
This is decided by some simple rules described in the [Auto-generation of Translatable Fields](/concept/translatable-fields-autogen)
explanation.

This guide describes how to override this behaviour partially or completely, both at the model level and within `StructBlock` definitions in StreamFields. Firstly, a quick explanation of what this configuration does.

## Types of translatable fields

### Translatable

On text fields, this means that the content of the field will be extracted for translation by editors.

On foreign keys, this means that the referenced model is translatable, and when the translation is created or updated,
the field on the translation will be automatically linked to the translation of the object referenced by the source.

On `StreamField`s, this means that any translatable fields will be extracted for translation, but some blocks may still
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

## Configuring translatable fields within StructBlocks

You can control which sub-fields of a `StructBlock` are translatable by defining a `translatable_blocks` attribute on the block class. This allows fine-grained control over which fields within a StreamField block should be extracted for translation.

### Basic usage

By default, all sub-fields within a `StructBlock` are considered translatable. You can override this by specifying a `translatable_blocks` list:

```python
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class CustomImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    description = blocks.CharBlock(required=False)

    # Only extract the description for translation
    # The image will be synchronized but not overridable per language
    translatable_blocks = ["description"]
```

In this example, only the `description` field will be extracted for translation. The `image` field will be synchronized across all language versions but won't appear in the translation interface.

### Excluding all fields from translation

You can prevent any fields from being extracted by using an empty list:

```python
class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False)
    code = blocks.TextBlock(required=False)

    # Don't extract any fields for translation
    translatable_blocks = []
```

This is useful for blocks like code snippets, `YouTubeBlock` embeds, or other technical content that shouldn't be translated.

### Managing image overridability

When working with images in `StructBlock` definitions, the `translatable_blocks` attribute controls whether images can be overridden per language:

```python
class LocationBlock(blocks.StructBlock):
    address = blocks.TextBlock(required=False, help_text="Locked across all languages")
    location_image = ImageChooserBlock(required=False, help_text="Can vary by language")

    # Only the image is overridable per language
    # The address is synchronized and locked
    translatable_blocks = ["location_image"]
```

In this example:
- The `location_image` is included in `translatable_blocks`, making it overridable. Editors can choose different images for different language versions.
- The `address` is excluded, meaning it will be synchronized across all languages and cannot be overridden in translations.

!!! warning "Image overridability considerations"

    If you exclude image fields from `translatable_blocks`, they will be synchronized across all language versions and editors won't be able to provide language-specific images. Only include image fields in `translatable_blocks` if you want to allow per-language image customization.

### Example: Default behavior vs explicit configuration

Here are three variations of the same block showing different behaviors:

```python
# Version 1: Default behavior (all fields translatable)
class CustomImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    description = blocks.CharBlock(required=False)
    # Both image and description are translatable/overridable


# Version 2: Only description is translatable
class CustomImageBlockDescriptionOnly(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    description = blocks.CharBlock(required=False)

    translatable_blocks = ["description"]
    # Image is synchronized, description is translatable


# Version 3: Both fields explicitly marked as translatable
class CustomImageBlockBothTranslatable(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    description = blocks.CharBlock(required=False)

    translatable_blocks = ["image", "description"]
    # Same as default, but explicit
```

### Integration with synchronized StreamFields

The `translatable_blocks` attribute works in conjunction with model-level field configuration. When a StreamField is marked as `SynchronizedField` at the model level, the `translatable_blocks` setting on individual blocks controls which sub-fields become overridable segments:

```python
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail_localize.fields import SynchronizedField, TranslatableField


class BlogPage(Page):
    # Regular translatable StreamField
    body = StreamField([
        ('image_block', CustomImageBlockDescriptionOnly()),
    ])

    # Synchronized StreamField
    sidebar = StreamField([
        ('image_block', CustomImageBlockDescriptionOnly()),
    ])

    translatable_fields = [
        TranslatableField("body"),  # Segments are translatable strings
        SynchronizedField("sidebar"),  # Segments are overridable (synchronized but editable)
    ]
```

In this configuration:
- In the `body` field, the `description` will be a translatable string
- In the `sidebar` field, the `description` will be an overridable segment (synchronized but can be customized per language)
- In both cases, the `image` field is excluded from `translatable_blocks`, so it won't be extracted at all

### Using `override_translatable_blocks` on child blocks

Similar to `override_translatable_fields` at the model level, you can use `override_translatable_blocks` on a block to partially override the default behavior of a parent block:

```python
class BaseImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=False)
    description = blocks.CharBlock(required=False)
    caption = blocks.CharBlock(required=False)


class CustomizedImageBlock(BaseImageBlock):
    # Override to only make caption translatable
    override_translatable_blocks = ["caption"]
```

!!! tip "Best practices"

    - Use `translatable_blocks = []` for technical blocks that should never be translated (code, URLs, identifiers)
    - Include image fields in `translatable_blocks` if you want editors to provide localized images
    - Exclude address or location-specific text fields if they should remain consistent across all languages
    - Remember that excluding a field from `translatable_blocks` means it will be synchronized across all translations and won't appear in the translation interface
