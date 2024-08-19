# Auto-generation of Translatable Fields

This document describes how Wagtail Localize automatically generates translatable fields from a model.

## 1. Check if `translatable_fields` attribute is defined

If the `translatable_fields` attribute is defined on the model, this whole process is bypassed.
See the [Configuring translatable fields](/how-to/field-configuration) guide for more information on how to set this attribute.

## 2. Discover fields on the model

The first step is to loop through all fields defined on the model. This is done at the Django ORM level rather than on panels.

The following are excluded:

-   Auto fields, such as `id`
-   Any field with `editable=False`
-   `ManyToManyField` and `ParentalKey`
-   Parent link fields, such as `page_ptr`
-   Inherited `MP_Node` fields named `path`, `depth`, and `numchild`
-   Inherited `Page` fields named `go_live_at`, `expire_at`, `first_published_at`, `content_type` and `owner`

Next, we look at text fields. All text fields (including `RichTextField` and `StreamField`) are set to translatable,
except for the following which are set to synchronised:

-   `URLField` and `EmailField`
-   `CharField` with `choices` set

`ForeignKey` and `OneToOneField` fields are set to translatable if the referenced model inherits from
`TranslatableMixin`, otherwise they are set to synchronised.

If the field defines a `get_translatable_segments` method, it is set to translatable.

All other fields that weren't excluded earlier are set to synchronised.

## 3. Discover child relationships on the model

Now we look at child relationships. These are relationships that are created by adding a `ParentalKey` from another model
to this one. They are commonly used for inline panels on pages.

If the current model is a page, we exclude the `comments` child relation as we do not want to synchronise or translate these.

If the child model inherits from `TranslatableMixin`, they are set as translatable. All others are set as synchronised.

## 4. Apply overrides

Finally we check for a `override_translatable_fields` attribute on the model, which allows a developer to change
the decisions that were automatically made. For example, they may want to make the `slug` field on pages synchronised
rather than translated.
