# 3. Translating content

Now that Wagtail Localize is fully configured, let's add some more interesting page models so that we can try out
some of Wagtail Localize's translation features.

## Blog app

Let's add a blog to our website! For this we need to create two page models, a "Blog post page" to represent blog
entries and a "Blog index page" to contain them.

Firstly, you should set up a new app for the models (it's best practise to group page types into separate Django apps):

``` shell
python manage.py startapp blog
```

Then, add this app into ``INSTALLED_APPS``:

``` python
INSTALLED_APPS = [
    'home',
    'search',
    # Insert this
    'blog',

    'wagtail_localize',
    'wagtail_localize.locales',

    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    # ...
]
```

Now, open ``blog/models.py`` and copy and paste the following code into it:

(this snippet is all standard Wagtail stuff, so I won't go into what it all means here!)

``` python
from django.db import models
from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel
from wagtail.core import blocks
from wagtail.core.fields import StreamField
from wagtail.core.models import Page, TranslatableMixin
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.snippets.edit_handlers import SnippetChooserPanel
from wagtail.snippets.models import register_snippet


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption = blocks.CharBlock(required=False)

    class Meta:
        icon = 'image'


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
        'wagtailimages.Image',
        on_delete=models.SET_NULL,
        null=True
    )
    body = StreamField(StoryBlock())
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blog_posts'
    )

    content_panels = Page.content_panels + [
        FieldPanel('publication_date'),
        ImageChooserPanel('image'),
        StreamFieldPanel('body'),
        SnippetChooserPanel('category'),
    ]

    parent_page_types = ['blog.BlogIndexPage']


class BlogIndexPage(Page):
    introduction = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    parent_page_types = ['home.HomePage']
```

Then add those models to the database:

``` shell
python manage.py makemigrations
python manage.py migrate
```

## Create some test pages

Next, let's create some test pages to translate. We will start by creating a blog index, then a blog post page under it.

Navigate to the English Home page in the explorer, click "Add child page" then click "Blog index page". Fill it in like
the following screenshot, and publish it.

![Blog index page being edited in Wagtail](/_static/tutorial/wagtail-blog-index-page.png)

Then navigate to the new blog index page, click "Add child page" then click "Blog post page". Fill it in how you like,
but make sure that you cover the following:

 - Upload an image and add it to the "Image" field
 - Create a "Blog Category" and select it in hte "Category" field
 - Add an item in the paragraph block, with some text and a couple of list items. Use some inline formatting
   (bold, italic, etc) and add a link

[Example](/_static/tutorial/wagtail-edit-source.png)

## Translate it!

Once you've published that, an exact copy should also be created in the French version too! remember when we selected
"English" in the "Sync from" field in the French locale earlier? This is what that field does.

When we add a template, it would be possible to visit this blog post in both the English and French versions of the
site. Both versions, however, will have the English content. Let's translate it into French!

To translate a page, find a foreign-language version of it in the page explorer and click "Edit". You should be
presented with the following message:

![Translate page](/_static/tutorial/wagtail-translate-page.png)

Can you guess the next step?

Hit that "Translate this page" button, then click "Submit" on the step afterwards, this will put that version of the page
into translation mode, and the editor should now look something like this:

[See image](/_static/tutorial/wagtail-edit-translation.png)

As you can see, the source page has been broken down into individual "Segments", there are three kinds of segments:


TODO, got a bit carried away here, move to explanation

### Text Segment

This is a snippet of translatable text that has been extracted from the page. For ``CharField``/``TextField``, this
snippet would contain the full value of the field (For example, the "title" field). ``StreamField``s and
``RichTextField``s are broken down into smaller segments, with block structure and embedded media removed.

``RichTextField``s still contain inline formatting and links, attributes are stripped out and replaced with ids to
prevent translators from changing them.

The main advantage of translating in this way, is it makes it very easy to keep the page up to date as the original
is edited over time. Translators only have to retranslate segments that were changed. Also, segment translations could
be reused to save time translating pages that have similar content.

### Overridable segment

By default, non-translatable content (such as images) stays in sync with the original page (this happens synchronously
with other translations, so images and their captions don't go out of sync).

But you can override this content, which can be useful if an image contains text, for example. When an overridable
segment is overridden, it stops syncing with the original page.

### Related object segment

If the page is linked with any translatable snippets, these are automatically submitted for translation with the page,
and the translation is automatically linked with the translated version of the snippet. Here, you can see the progress
of translating this snippet, with a link to edit the snippet.
