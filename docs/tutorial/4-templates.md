# 4. Translating templates

In this section, we will create a template for the blog posts and explore some of the features that Wagtail provides
for internationalised sites.

Wagtail Localize is a translation editor on top of Wagtail's builtin internationalisation features so everything
described in this section will work without Wagtail Localize installed. We've added this to the tutorial in order to
provide a well-rounded introduction to implementing an internationalised site with Wagtail.

## Creating a template for blog post

Let's add a simple template for the blog post so we can view its content on the frontend.
Create a new file called `blog_post_page.html` in a folder called `blog/templates/blog`
(note, you will need to create the `templates` and `blog` folders). Then insert the
following:

```html+Django
{% load i18n wagtailimages_tags %}

<h1>{{ page.title }}</h1>

<p>{% translate "Category" %}: <b>{{ page.category }}</b></p>

{% image page.image max-200x200 %} {{ page.body }}
```

Then, find your blog post page you created in the admin, and click "View live". If you don't see the "View live" link,
make sure you've published the page first.

![Blog post page on the frontend](/_static/tutorial/blog-post-frontend.png)

The French translation should look like the following (assuming you've translated it):

![Blog post page French translation on the frontend](/_static/tutorial/blog-post-frontend-translated.png)

As you can see, we're most of the way there with a very simple template. Wagtail uses separate pages for each language,
so you don't usually have to make any changes to the templates to support translated content (apart from adding
`{% translate %}` tags around any static text).

!!! note "Translating static text"

    Static text in templates, such as the word "Category" in the above example, should be translated using
    [Django's built-in translation tools](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/).

## Adding a language switcher

One feature that almost all translated sites will have is a widget to allow users to switch to other translations of
the page.

Let's add a simple language switcher. Add the following snippet of code into the `blog_post_page.html` template:

<!-- prettier-ignore-start -->
```html+Django
{# make sure these are at the top of the file #}
{% load i18n wagtailcore_tags %}

{% if page %}
    {% for translation in page.get_translations.live %}
        {% get_language_info for translation.locale.language_code as lang %}
        <a href="{% pageurl translation %}" rel="alternate" hreflang="{{ lang.code }}">
            {{ lang.name_local }}
        </a>
    {% endfor %}
{% endif %}
```
<!-- prettier-ignore-end -->

This example was taken from the Wagtail docs, have a look [there](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html#basic-example) for a full explanation of this example.

Here's how it should look, the link should take you to the French version, then back again:

![Blog post page on the frontend with link to french version](/_static/tutorial/blog-post-frontend-with-link.png)

## Filtering search results by language

Finally, let's turn our attention to the search view on the site. Wagtail adds a default search view to project when
it's created in `search/views.py`. You can find the search view by navigating to `/en/search/` in your browser.

To test this, try searching for "blog":

![Search on both languages](/_static/tutorial/search-unfiltered.png)

This has returned French results even though we are visiting the English search page!

To make it filter out pages from other langauges, we just need to make it filter pages by their `locale` field against
the currently active language which can be found with `Locale.get_active()`.

To implement this, open up `search/views.py` in your favourite editor, then modify the following lines:

-   Change the import line `from wagtail.models import Page` to `from wagtail.models import Page, Locale`
-   Change the query `Page.objects.live().search(search_query)` to `Page.objects.live().filter(locale=Locale.get_active()).search(search_query)`

Refresh the search page in the browser, the results should now be filtered.
