# 3. Translating content

In this section, you will add some test content into the site and translate it with Wagtail Localize.

## Blog app

Let's create a blog! A simple blog needs at least two page models, a "Blog post page" to represent blog entries and a
"Blog index page" to contain them. Let's also create a "Blog category" snippet so we can demonstrate translating
snippets.

Firstly, start a new app for the blog models:

```shell
python manage.py startapp blog
```

Then, add this app into `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "home",
    "search",
    # Insert this
    "blog",
    "wagtail_localize",
    "wagtail_localize.locales",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    # ...
]
```

Now, open `blog/models.py` and copy and paste the following code into it:

```python
from django.db import models
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page, TranslatableMixin
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.models import register_snippet


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)

    class Meta:
        icon = "image"


class StoryBlock(blocks.StreamBlock):
    heading = blocks.CharBlock()
    paragraph = blocks.RichTextBlock()
    image = ImageBlock()


@register_snippet
class BlogCategory(TranslatableMixin):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class BlogPostPage(Page):
    publication_date = models.DateField(null=True, blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image", on_delete=models.SET_NULL, null=True
    )
    body = StreamField(StoryBlock())
    category = models.ForeignKey(
        BlogCategory, on_delete=models.SET_NULL, null=True, related_name="blog_posts"
    )

    content_panels = Page.content_panels + [
        FieldPanel("publication_date"),
        FieldPanel("image"),
        FieldPanel("body"),
        FieldPanel("category"),
    ]

    parent_page_types = ["blog.BlogIndexPage"]


class BlogIndexPage(Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("introduction"),
    ]

    parent_page_types = ["home.HomePage"]
```

Then add those models to the database by running the following commands in your terminal:

```shell
python manage.py makemigrations
python manage.py migrate
```

## Create some test pages

Now you can create some test pages to translate! Let's start by creating a blog index, then a blog post page under it.

Navigate to the English Home page in the explorer, click "Add child page" then click "Blog index page". Fill it in like
the following screenshot, and publish it.

![Blog index page being edited in Wagtail](/_static/tutorial/wagtail-blog-index-page.png)

Then navigate to the new blog index page, click "Add child page" then click "Blog post page". Fill it in how you like,
but make sure that you cover the following:

-   Upload an image and add it to the "Image" field
-   Create a "Blog Category" and select it in the "Category" field
-   Add an item in the paragraph block, with some text and a couple of list items. Use some inline formatting
    (bold, italic, etc) and add a link

![Blog post page being edited in Wagtail](/_static/tutorial/wagtail-edit-source.png)

## Translate it!

Once those pages are created and published, aliases of those pages should be automatically created in the French version!
This is because we set the "Sync from" field to "English" when we created the French locale. This tells Wagtail Localize
to sync all new pages as well as the pages that existed at the time.

At the moment, the French pages are an exact copy of the English pages, so let's translate them into French!

To translate the blog post you just created, find the French language of it in the page explorer and click edit.
Alternatively, you can go straight from editing the English version to the French using the language selector at the top
of the editor.

When you get to the edit view, you will get this message (this is because it is keeping itself in sync with the English
page):

![Translate page](/_static/tutorial/wagtail-translate-page.png)

Hit that "Translate this page" button, then click "Submit" on the step afterwards, this will put the page into translation
mode, and the editor should now look something like this:

![Blog post page being translated in Wagtail](/_static/tutorial/wagtail-edit-translation.png)

As you can see, each segment of translatable text has been extracted into a separate editable block.
Translating in this way makes it easier to keep the translations in sync with the original page, as editors only need to
retranslate changed segments when the original page is updated.

There are three kinds of segment that you can edit here:

### 1. String segments

String segments are translatable pieces of text which are extracted from text fields on the page. Rich text fields are
broken down into smaller segments to make it easier for translators to translate them.

String segments can be individually translated through this UI, by downloading/uploading PO files (using the buttons at
the top of the editor), using a [machine translation service](/how-to/integrations/machine-translation) or an
[external translation tool](/how-to/integrations/pontoon).

![A translated string segment](/_static/tutorial/wagtail-translated-segment.png)

### 2. Overridable segments

These segments are used to represent non-text fields that may be changed for each language. Examples of this include
images, choice fields, and non-translatable string fields (such as usernames, email addresses, etc).

These segments will always default to the same value as in the original. But editors may override these values which
breaks this link.

![A overridden image](/_static/tutorial/wagtail-overridden-image.png)

### 3. Related object segments

Any translatable related objects that are linked to the original page are automatically submitted for translation when
the page is submitted. For example, the `BlogCategory` model is translatable, so Wagtail Localize has automatically
submitted the "Dog" blog category, that was linked from the original page, for translation:

![A translated blog category](/_static/tutorial/wagtail-translated-snippet.png)

Clicking "Edit" here will take the user to the translation editor of the "Dogs" snippet:

![Snippet being translated in Wagtail](/_static/tutorial/wagtail-edit-snippet-translation.png)

!!! note "Stopping translation mode"

    If you would like to make significant changes to the translation, you can stop the translation mode by clicking the
    "Stop Synced translation" action in the action menu at the bottom:

    ![Stop translation button in action menu](/_static/tutorial/wagtail-stop-translation.png)

    After clicking this, the page will switch to using the standard Wagtail editor. It will still be connected to the
    original, so you can still use the language switcher at the top of the page to find the original page and other
    translations.

    You can restart translation mode later by clicking "Start Synced translation" in the action menu. This will override any
    changes made while translation mode was stopped.

    While translation mode is stopped, editors will need to synchronise any content updates from the source manually.
