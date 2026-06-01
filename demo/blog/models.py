from django.contrib import messages
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from taggit.models import Tag, TaggedItemBase
from wagtail.admin.panels import (
    FieldPanel,
    MultiFieldPanel,
    MultipleChooserPanel,
    PublishingPanel,
)
from wagtail.api import APIField
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.fields import StreamField
from wagtail.models import (
    DraftStateMixin,
    Orderable,
    Page,
    PreviewableMixin,
    RevisionMixin,
)
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from blog.blocks import BaseStreamBlock


@register_snippet
class Person(
    DraftStateMixin,
    RevisionMixin,
    PreviewableMixin,
    index.Indexed,
    ClusterableModel,
):
    """Blog author (snippet), linked from blog posts via `BlogPersonRelationship`."""

    first_name = models.CharField("First name", max_length=254)
    last_name = models.CharField("Last name", max_length=254)
    job_title = models.CharField("Job title", max_length=254)

    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    revisions = GenericRelation(
        "wagtailcore.Revision",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="person",
        for_concrete_model=False,
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("first_name"),
                FieldPanel("last_name"),
            ],
            "Name",
        ),
        FieldPanel("job_title"),
        FieldPanel("image"),
        PublishingPanel(),
    ]

    search_fields = [
        index.SearchField("first_name"),
        index.SearchField("last_name"),
        index.FilterField("job_title"),
        index.AutocompleteField("first_name"),
        index.AutocompleteField("last_name"),
    ]

    api_fields = [
        APIField("first_name"),
        APIField("last_name"),
        APIField("job_title"),
        APIField("image"),
    ]

    @property
    def thumb_image(self):
        return self.image.get_rendition("fill-50x50").img_tag() if self.image else ""

    @property
    def preview_modes(self):
        return PreviewableMixin.DEFAULT_PREVIEW_MODES + [("blog_post", _("Blog post"))]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_preview_template(self, request, mode_name):
        from blog.models import BlogPage

        if mode_name == "blog_post":
            return BlogPage.template
        return "blog/preview/person.html"

    def get_preview_context(self, request, mode_name):
        from blog.models import BlogPage

        context = super().get_preview_context(request, mode_name)
        if mode_name == self.default_preview_mode:
            return context

        page = BlogPage.objects.filter(blog_person_relationship__person=self).first()
        if page:
            page.authors = [
                self if author.pk == self.pk else author for author in page.authors()
            ]
            if not self.live:
                page.authors.append(self)
        else:
            page = BlogPage.objects.first()
            if page:
                page.authors = [self]

        if page is not None:
            context["page"] = page
        return context

    class Meta:
        verbose_name = "person"
        verbose_name_plural = "people"


class BlogPersonRelationship(Orderable, models.Model):
    page = ParentalKey(
        "blog.BlogPage",
        related_name="blog_person_relationship",
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        "blog.Person", related_name="person_blog_relationship", on_delete=models.CASCADE
    )
    panels = [FieldPanel("person")]

    api_fields = [
        APIField("page"),
        APIField("person"),
    ]

    def __str__(self):
        return f"{self.page} - {self.person}"


class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "blog.BlogPage", related_name="tagged_items", on_delete=models.CASCADE
    )


class BlogPage(Page):
    introduction = models.TextField(help_text="Text to describe the page", blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Landscape mode only; horizontal width between 1000px and 3000px.",
    )
    body = StreamField(
        BaseStreamBlock(), verbose_name="Page body", blank=True, use_json_field=True
    )
    subtitle = models.CharField(blank=True, max_length=255)
    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)
    date_published = models.DateField("Date article published", blank=True, null=True)

    content_panels = Page.content_panels + [
        FieldPanel("subtitle"),
        FieldPanel("introduction"),
        FieldPanel("image"),
        FieldPanel("body"),
        FieldPanel("date_published"),
        MultipleChooserPanel(
            "blog_person_relationship",
            chooser_field_name="person",
            heading="Authors",
            label="Author",
            panels=None,
            min_num=1,
        ),
        FieldPanel("tags"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("body"),
    ]

    api_fields = [
        APIField("introduction"),
        APIField("image"),
        APIField("body"),
        APIField("subtitle"),
        APIField("tags"),
        APIField("date_published"),
        APIField("blog_person_relationship"),
    ]

    def authors(self):
        return [
            n.person
            for n in self.blog_person_relationship.filter(
                person__live=True
            ).select_related("person")
        ]

    @property
    def get_tags(self):
        tags = self.tags.all()
        base_url = self.get_parent().url
        for tag in tags:
            tag.url = f"{base_url}tags/{tag.slug}/"
        return tags

    parent_page_types = ["blog.BlogIndexPage"]
    subpage_types = []


class BlogIndexPage(RoutablePageMixin, Page):
    introduction = models.TextField(help_text="Text to describe the page", blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Landscape mode only; horizontal width between 1000px and 3000px.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("introduction"),
        FieldPanel("image"),
    ]

    api_fields = [
        APIField("introduction"),
        APIField("image"),
    ]

    subpage_types = ["blog.BlogPage"]
    parent_page_types = ["home.HomePage"]

    def children(self):
        return self.get_children().specific().live()

    def get_context(self, request):
        context = super().get_context(request)
        context["posts"] = (
            BlogPage.objects.descendant_of(self).live().order_by("-date_published")
        )
        return context

    @route(r"^tags/$", name="tag_archive")
    @route(r"^tags/([\w-]+)/$", name="tag_archive")
    def tag_archive(self, request, tag=None):
        try:
            tag = Tag.objects.get(slug=tag)
        except Tag.DoesNotExist:
            if tag:
                msg = f'There are no blog posts tagged with "{tag}"'
                messages.add_message(request, messages.INFO, msg)
            return redirect(self.url)

        posts = self.get_posts(tag=tag)
        context = {
            "self": self,
            "page": self,
            "tag": tag,
            "posts": posts,
        }
        return render(request, "blog/blog_index_page.html", context)

    def serve_preview(self, request, mode_name):
        return self.serve(request)

    def get_posts(self, tag=None):
        posts = BlogPage.objects.live().descendant_of(self)
        if tag:
            posts = posts.filter(tags=tag)
        return posts

    def get_child_tags(self):
        tags = []
        for post in self.get_posts():
            tags += post.get_tags
        tags = sorted(set(tags))
        return tags
