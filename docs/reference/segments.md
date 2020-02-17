# Segment extraction and ingestion

The translation module performs translation by breaking the page/snippet up into small translatable snippets called "segments".

The segment extraction takes a page or regular model and pulls out segments, templates and related objects. These are described as follows:

 - **Segments**
   A segment is be the entire value of a field/block or a paragraph in a ``RichTextField`` or ``RichTextBlock``.

   Each segment represents an individual block of text, so they cannot contain block elements such as images.
   But they can contain inline elements such as links and inline text formatting.

 - **Templates**
   When segments are extracted from a ``RichTextField`` or ``RichTextBlock`` they leave the surrounding HTML that contains the structure and any other block elements such as images or embeds behind.
   These parts are also extracted and stored in translation memory with any translatable text segments that were extracted.
   The template is used to generate the final value of the translated ``RichTextField`` or ``RichTextBlock`` when translations come in

 - **Related objects**
   Translatable objects that are linked to from this object by Foreign Key need to be translated before this object can be.
   So we need to know about them.

## Segment value types

Segment value types are used to represent source/translated segments in Python code after they have been extracted from an object or before they are going to be ingested to make a translation.

All of these types are importable from `wagtail_localize.translation.segments`.

### `SegmentValue`

`wagtail_localize.translation.segments.SegmentValue`

A text or HTML value.

### `TemplateValue`

`wagtail_localize.translation.segments.TemplateValue`

Rich text

### `RelatedObjectValue`

`wagtail_localize.translation.segments.RelatedObjectValue`

Any foreign keys to translatable objects

## Functions

### `extract_segments`

`wagtail_localize.translation.segments.extract.extract_segments`

### `ingest_segments`

`wagtail_localize.translation.segments.extract.ingest_segments`

## HTML utilities

### extract_html_segments

### restore_html_segments

### extract_html_elements

### restore_html_elements
