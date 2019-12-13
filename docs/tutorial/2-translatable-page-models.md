# Translatable page models

In this section of the tutorial, we will make the `HomePage` model translatable, we will then add a new `BlogPage` model which will hold the blog posts on our site.

## Making `HomePage` translatable

For this tutorial we won’t have any translatable content on the homepage, but we should still make the `HomePage` translatable as having a separate homepage for each language is useful for organising the pages in the admin.

To make the `HomePage` translatable, open `home/models.py` and add `TranslatablePageMixin` to the `HomePage` class:


    from django.db import models

    from wagtail.core.models import Page
    from wagtail_localize.models import TranslatablePageMixin


    class HomePage(TranslatablePageMixin, Page):
        pass

This class adds the fields and methods necessary to allow us to tell which language each instance of the page is in but also allows us to find instances of the page in foreign languages (which will be important for `BlogPage`).

It’s probably worth mentioning that this isn’t the usual way to add `TranslatablePageMixin` to an exisiting page model, but doing it this way will work here as `HomePage` only has one instance. If you plan on making an existing site translatable, please refer to the how to guide. TODO LINK

## Adding a `BlogPage` model

Now let’s add a new `BlogPage` model which we will use for our blog post content. I’ve added this to the existing `home/models.py` file, to keep this tutorial concise (but you can add a separate app if you want to!)


    # Add to the top of the file
    from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel
    from wagtail.core import blocks
    from wagtail.core.fields import StreamField
    from wagtail.images.edit_handlers import ImageChooserPanel


    # ...


    # Add after HomePage
    class BlogPage(TranslatablePageMixin, Page):
        introduction = models.TextField()
        image = models.ForeignKey(
            'wagtailimages.Image',
            on_delete=models.SET_NULL,
            null=True,
            blank=True
        )
        body = StreamField([
            ('heading', blocks.CharBlock()),
            ('paragraph', blocks.RichTextBlock()),
        ])

        content_panels = Page.content_panels + [
            FieldPanel('introduction'),
            ImageChooserPanel('image'),
            StreamFieldPanel('body'),
        ]

To apply these model changes to the database, run the following:


    python manage.py makemigrations
    python manage.py migrate

Now lets add a simple template so we can view blog posts on the frontend, save the following template as `home/templates/home/blog_page.html`:

    {% extends "base.html" %}
    {% load static wagtailimages_tags %}
    {% block body_class %}template-blogpage{% endblock %}
    {% block content %}
        <h1>{{ page.title }}</h1>
        <p>{{ page.introduction }}</p>
        {% image page.image original %}
        {% for block in page.body %}
            {% if block.block_type == 'heading' %}
                <h2>{{ block.value }}</h2>
            {% else %}
                {{ block.render }}
            {% endif %}
        {% endfor %}
    {% endblock content %}


You can now go ahead an add an example blog post or two underneath your homepage in Wagtail. In the next section we will look at implementing a workflow for allowing editors to translate pages in the next section.
