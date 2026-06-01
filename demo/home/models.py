from blog.blocks import BaseStreamBlock
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, PageChooserPanel
from wagtail.fields import StreamField
from wagtail.models import Page


class HomePage(Page):
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Homepage image",
    )
    hero_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Write an introduction for the site",
    )
    hero_cta = models.CharField(
        verbose_name="Hero CTA",
        max_length=255,
        blank=True,
        help_text="Text to display on Call to Action",
    )
    hero_cta_link = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Hero CTA link",
        help_text="Choose a page to link to for the Call to Action",
    )

    body = StreamField(
        BaseStreamBlock(),
        verbose_name="Home content block",
        blank=True,
        use_json_field=True,
    )

    featured_section_3_title = models.CharField(
        blank=True,
        max_length=255,
        help_text="Heading for the blog featured section",
    )
    featured_section_3 = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Blog index page; up to six child posts are shown on the homepage.",
        verbose_name="Featured section (blog)",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("image"),
                FieldPanel("hero_text"),
                FieldPanel("hero_cta"),
                PageChooserPanel("hero_cta_link"),
            ],
            "Hero",
        ),
        FieldPanel("body"),
        MultiFieldPanel(
            [
                FieldPanel("featured_section_3_title"),
                PageChooserPanel("featured_section_3"),
            ],
            "Blog section",
        ),
    ]

    subpage_types = ["blog.BlogIndexPage"]
