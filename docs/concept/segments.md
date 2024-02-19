# Segments

When pages are submitted for translation, the content is broken down into 'segments'.
Translation is performed on individual segments rather than the page as a whole.

It's done this way to allow translations to be updated incrementally. If a single
field/block/paragraph is updated in the source, translators will only have to update
a single segment and not the whole page.

Not all segments are strings of text to be translated, all of the segment types are listed below.

## Segment types

### String Segment

![Screenshot of string segment](/_static/segment-types/string.png)

This is a snippet of translatable text that has been extracted from the page. For `CharField`/`TextField`, this
snippet would contain the full value of the field (For example, the "title" field). `StreamField`s and
`RichTextField`s are broken down into smaller segments, with block structure and embedded media removed.

`RichTextField`s still contain inline formatting and links, attributes are stripped out and replaced with ids to
prevent translators from changing them.

The main advantage of translating in this way, is it makes it very easy to keep the page up to date as the original
is edited over time. Translators only have to retranslate segments that were changed. Also, segment translations could
be reused to save time translating pages that have similar content.

### Template Segment

These are not displayed anywhere in the editor. But instead, here is an example of how they look in the database:

```html
<h1><text position="0"></h1>
<p>
    <text position="1">
    <ul>
        <li><b><text position="2"></b></li>
    </ul>
</p>
```

This segment type is used for translating rich fext fields/blocks.

Each heading, paragraph, and list item in rich text is extracted as a separate string segment.
In order to be able to recombine these for the translation, we also need to store the structure of
block and any non-translatable elements such as images or embeds.

Template Segments are HTML blobs that contain everything around the extracted string segments. The
string segments are replaced with `<text>` tags marking the positions of where the translated
string segments need to be inserted.

If you combined the above template with the following string segments:

-   `The Heading`
-   `A paragraph with some <b>Bold text</b>`
-   `A list item`

This would produce the following rich text value:

```html
<h1>The Heading</h1>
<p>
    A paragraph with some <b>Bold text</b>
    <ul>
        <li><b>A list item</b></li>
    </ul>
</p>
```

Note that inline tags (`<b>`, `<a>`, etc) are extracted with the string segments and all block tags
(`<p>`, `<li>`, `<h1>`, etc) are left behind. If an inline tag completely encapsulates a string
segment, that inline tag is left in the template (see the `<b>` tag in the `<li>` tag above).

### Related Object Segment

![Screenshot of related object segment](/_static/segment-types/related-object.png)

This segment type represents a related object that is translatable. These are extracted from `ForeignKey`,
`OneToOneField`, or `SnippetChooserBlock`s that reference a translatable model.

When a page is submitted for translation, any translatable related objects are automatically submitted for translation
with the page, and the translated pages is automatically linked with the translated version of the related object.
Here, you can see the progress of translating this related object, with a link to edit the related object.

### Overridable Segment

![Screenshot of overridable segment](/_static/segment-types/overridable.png)

This segment type represents any field that can be changed per-locale. Unlike string segments, they don't have
to be changed and they also don't have to be text fields either. By default, they are kept in sync with the original
but a user can optionally override them with something else. When they are overridden, any changes to the original
page are ignored.

All fields configured with the [`SynchronisedField`](/ref/translatable-fields/#wagtail_localize.fields.SynchronizedField)
field type will be extracted as an overridable segment.
