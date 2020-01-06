# Translation memory

The translation memory module is responsible for tracking which pages have been submitted to an external translation system, keeping track of translation progress, building the translated pages when translations come in and storing a mapping of source strings to translations for future use.

This document gives an overview of the models in this module.

# Translatable objects

A translatable object is a language-agnostic representation of something in the database that could be translated, such as a page or a snippet.

All instances of a page/snippet that are translations of each other are represented with a single instance of `TranslatableObject`.

This is used by the other models to reference translatable objects in a language-agnostic way.

# Translation contexts

A translation context is a field inside a translatable object that can be translated. These are used to identify the location of a translation, allowing different translations to be used on different parts of the page even if they have the same value on the source.

Examples of contexts are:

 - Model fields
 - Streamfield blocks
 - Inline panel items
 - Fields in struct blocks and inline panel items

TODO: Graphic highlighting the contexts on a page?

In the database, contexts are represented as a reference to a translatable object and a content path

## Content paths

Content Paths are used to identify a context within an object. As Wagtail pages have nested fields (streamfield blocks and inline panel objects), we use a dotted path to an individual part of the page.

For example:

 - A field: `title`
 - A StreamField block: `body.<Block ID>` (all streamfield blocks are assigned a UUID by Wagtail)
 - A StructBlock field: `body.<Block ID>.struct_field`
 - An InlinePanel item: `image_carousel.<Translation Key>.image_caption` (InlinePanel models must inherit from `TranslatableMixin` so that they have a `translation_key` field)

# Segments

A segment is a piece of text that has been extracted from a page for translation; they are stored in the `Segment` model.
The `Segment` model only stores each unique segment of text once.

All segments are stored in HTML format even if they came from a text field. if they came from a plain text field, any special characters are escaped before storing them.

Segments can only contain inline HTML tags (such as `<a>`, `<b>`, `<span>`). They may not contain any block tags (such as `<div>`, `<p>`).

# Translations

The `SegmentTranslation` table stores all previous translations of a segment for each language and context. We store translations so that we can pre-fill translation requests if the page is changed, so only the parts of the page that have been updated need to be translated. We also use previous translations to pre-fill translations on new pages as well (fuzzy matching).

# Templates

Templates are used when translating rich text fields. Not all of the content within a rich text field is translatable (such as block tags, images, etc), so the template contains the untranslatable content with the translatable parts replaced with `<text>` tags. When the translated version of the page is built, the template is retrieved from the database and the `<text>` tags are replaced with the translated strings.

For example, when the following HTML field is processed for translation:

```html
<h1>Some rich text</h1>
<p>A paragraph with <a href="http://example.com">a link</a> and some <b>bold text</b>.</p>
<img src="...">
```

The following segments are extracted:

 - `Some rich text`
 - `A paragraph with <a id="a1">a link</a> and some <b>bold text</b>.`
   (note, HTML attributes are extracted and stored separately)

And the following template is generated:

```html
<h1><text position="0"></h1>
<p><text position="1"></p>
<img src="...">
```

When those two segments are translated, the template is used to combine them to create the translated HTML.

# Translatable revisions

A translatable revision is similar to `PageRevision` in Wagtail, except it is generic (works for snippets as well as pages) and is only used when the page/snippet has been submitted for translation.

The translatable revision contains a copy of all the content of the page/snippet at the point it was submitted for translation, this content is used to set any synchronised fields when the translation is generated.

# Location models

The location models link translatable revisions to segments, translations and related objects.

All location models contain the following fields:

 - `source` - A foreign key to the translation source
 - `context` - A foreign key to the translation context
 - `order` - An integer showing the position on the page. This allows the segments to be submitted for translation in the same order that they appear in Wagtail.

## SegmentLocation

Links segments to locations on the source. This model has two extra fields:

 - `segment` A foreign key to the source segment
 - `html_attrs` A JSON formatted text field containing any HTML attributes that have been stripped out of inline tags

For example, say we have a `title` field that contains "My page" we would represent this as follows:

```python
SegmentLocation(
    source=<the source>
    context=TranslationContext(
        object=<the page>
        path="title"
    )
    order=1
    segment=Segment("My page")
    html_attrs="{}"
)
```

## TemplateLocation

Links templates to locations on the source. Templates and the segments they contain all share the same context. The ordering of the segments by the `order` field determines the position the segments are in the template.

To help demonstrate, when a HTML field containing ``<h1>my <a id="http://www.wagtail.io/">page</a></h1>`` is submitted for translation, the following locations will be saved into translation memory:

```python
TemplateLocation(
    source=<the source>
    context=TranslationContext(
        object=<the page>
        path="body"
    )
    order=1
    template=Template('<h1><text position="0"></h1>')
)

SegmentLocation(
    source=<the source>
    context=TranslationContext(
        object=<the page>
        path="body"
    )
    order=2
    html_attrs='{
        "a1": {
            "href": "http://www.wagtail.io/"
        }
    }'
    segment=Segment('My <a id="a1">page</a>')
)
```

## RelatedObjectLocation

Links translatable related objects to locations on the source. This lets us know which fields reference a translatable related object so we can link the translated version when the page is translated. It's also used to allow us to tell what snippets/images a page depends on before generating the translation so we can make sure those are translated first.
