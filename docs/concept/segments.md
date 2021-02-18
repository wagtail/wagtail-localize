# Segments

When pages are submitted for translation, the content is broken down into 'segments'.
Translation is performed on individual segments rather than the page as a whole.

It's done this way to allow translations to be updated incremantally. If a single
field/block/paragraph is updated in the source, translators will only have to update
a single segment and not the whole page.

Not all segments are strings of text to be translated, all of the segment types are listed below.

## Segment types

### String Segment

This segment type represents a string of translatable text.

![Screenshot of string segment](/_static/segment-types/string.png)

### Template Segment

This segment type is used for translating rich fext fields/blocks.

Each heading, paragraph, and list item in rich text is extracted as a separate string segment.
In order to be able to recombine these for the translation, we also need to store the structure of
block and any non-translatable elements such as images or embeds.

Template Segments are HTML blobs that contain everything around the extracted string segments. The
string segments are replaced with ``<text>`` tags marking the positions of where the translated
string segments need to be inserted.

They are not displayed anywhere in the editor. But instead, here is an example of how they look in the database:

```html
<h1><text position="0"></h1>
<p>
    <text position="1">
    <ul>
        <li><b><text position="2"></b></li>
    </ul>
</p>
```

If you combined this template with the following string segments:

 - ``The Heading``
 - ``A paragraph with some <b>Bold text</b>``
 - ``A list item``

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

Note that inline tags (``<b>``, ``<a>``, etc) are extracted with the string segments and all block tags
(``<p>``, ``<li>``, ``<h1>``, etc) are left behind. If an inline tag completely encapsulates a string
segment, that inline tag is left in the template (see the ``<b>`` tag in the  ``<li>`` tag above).

### Related Object Segment

This segment type represents a related object that is translatable. These are extracted from ``ForeignKey``,
``OneToOneField``, or ``SnippetChooserBlock``s that reference a translatable model.

If you use one of those types but reference a non-translatable model, it would be extracted as an
[Overridable Segment](#overridable-segment) instead.

![Screenshot of related object segment](/_static/segment-types/related-object.png)

### Overridable Segment

This segment type represents any field that can be changed per-locale. Unlike string segments, they don't have
to be changed and they also don't have to be text fields either.

All fields configured with the [``SynchronisedField``](/ref/translatable-fields/#wagtail_localize.fields.SynchronizedField)
field type will be extracted as an overridable segment.

![Screenshot of overridable segment](/_static/segment-types/overridable.png)
