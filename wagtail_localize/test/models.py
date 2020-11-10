from django.db import models
from django.utils.translation import gettext_lazy as __

from modelcluster.fields import ParentalKey
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page, Orderable, TranslatableMixin
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.models import register_snippet

from wagtail_localize.fields import TranslatableField, SynchronizedField
from wagtail_localize.segments import StringSegmentValue


@register_snippet
class TestSnippet(TranslatableMixin, models.Model):
    field = models.TextField(__("field"))

    translatable_fields = [TranslatableField("field")]


@register_snippet
class NonTranslatableSnippet(models.Model):
    field = models.TextField()


class TestStructBlock(blocks.StructBlock):
    field_a = blocks.TextBlock()
    field_b = blocks.TextBlock()


class TestNestedStreamBlock(blocks.StreamBlock):
    block_a = blocks.TextBlock()
    block_b = blocks.TextBlock()


class CustomStructBlock(blocks.StructBlock):
    field_a = blocks.TextBlock()
    field_b = blocks.TextBlock()

    def get_translatable_segments(self, value):
        return [
            StringSegmentValue("foo", "{} / {}".format(value["field_a"], value["field_b"]))
        ]

    def restore_translated_segments(self, value, segments):
        for segment in segments:
            if segment.path == "foo":
                field_a, field_b = segment.render_text().split("/")
                value["field_a"] = field_a.strip()
                value["field_b"] = field_b.strip()

        return value


class CustomBlockWithoutExtractMethod(blocks.Block):
    pass


class TestStreamBlock(blocks.StreamBlock):
    test_charblock = blocks.CharBlock(max_length=255)
    test_textblock = blocks.TextBlock(label=__("text block"))
    test_emailblock = blocks.EmailBlock()
    test_urlblock = blocks.URLBlock()
    test_richtextblock = blocks.RichTextBlock()
    test_rawhtmlblock = blocks.RawHTMLBlock()
    test_blockquoteblock = blocks.BlockQuoteBlock()
    test_structblock = TestStructBlock()
    test_listblock = blocks.ListBlock(blocks.TextBlock())
    test_nestedstreamblock = TestNestedStreamBlock()
    test_customstructblock = CustomStructBlock()
    test_customblockwithoutextractmethod = CustomBlockWithoutExtractMethod()
    test_pagechooserblock = blocks.PageChooserBlock()
    test_imagechooserblock = ImageChooserBlock()
    test_documentchooserblock = DocumentChooserBlock()
    test_snippetchooserblock = SnippetChooserBlock(TestSnippet)


class TestCustomField(models.TextField):
    def get_translatable_segments(self, value):
        if not value:
            # Don't disrupt other tests
            return []

        return [StringSegmentValue("foo", "{} and some extra".format(value))]


class TestPage(Page):
    test_charfield = models.CharField(__("char field"), max_length=255, blank=True, null=True, default='')
    test_textfield = models.TextField(blank=True)
    test_emailfield = models.EmailField(blank=True)
    test_slugfield = models.SlugField(blank=True)
    test_urlfield = models.URLField(blank=True)

    test_richtextfield = RichTextField(blank=True)
    test_streamfield = StreamField(TestStreamBlock, blank=True)

    test_snippet = models.ForeignKey(
        TestSnippet, null=True, blank=True, on_delete=models.SET_NULL
    )

    test_customfield = TestCustomField(blank=True)

    test_synchronized_charfield = models.CharField(max_length=255, blank=True)
    test_synchronized_textfield = models.TextField(blank=True)
    test_synchronized_emailfield = models.EmailField(blank=True)
    test_synchronized_slugfield = models.SlugField(blank=True)
    test_synchronized_urlfield = models.URLField(blank=True)

    test_synchronized_richtextfield = RichTextField(blank=True)
    test_synchronized_streamfield = StreamField(TestStreamBlock, blank=True)

    test_synchronized_image = models.ForeignKey(
        'wagtailimages.Image', null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    test_synchronized_document = models.ForeignKey(
        'wagtaildocs.Document', null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    test_synchronized_snippet = models.ForeignKey(
        TestSnippet, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    test_synchronized_customfield = TestCustomField(blank=True)

    translatable_fields = [
        TranslatableField("test_charfield"),
        TranslatableField("test_textfield"),
        TranslatableField("test_emailfield"),
        TranslatableField("test_slugfield"),
        TranslatableField("test_urlfield"),
        TranslatableField("test_richtextfield"),
        TranslatableField("test_streamfield"),
        TranslatableField("test_snippet"),
        TranslatableField("test_childobjects"),
        TranslatableField("test_customfield"),
        SynchronizedField("test_synchronized_charfield"),
        SynchronizedField("test_synchronized_textfield"),
        SynchronizedField("test_synchronized_emailfield"),
        SynchronizedField("test_synchronized_slugfield"),
        SynchronizedField("test_synchronized_urlfield"),
        SynchronizedField("test_synchronized_richtextfield"),
        SynchronizedField("test_synchronized_streamfield"),
        SynchronizedField("test_synchronized_image"),
        SynchronizedField("test_synchronized_document"),
        SynchronizedField("test_synchronized_snippet"),
        SynchronizedField("test_synchronized_childobjects"),
        SynchronizedField("test_synchronized_customfield"),
    ]


class TestModel(TranslatableMixin):
    title = models.CharField(max_length=255)
    test_charfield = models.CharField(max_length=255, blank=True)
    test_textfield = models.TextField(blank=True)
    test_emailfield = models.EmailField(blank=True)

    translatable_fields = [
        TranslatableField("test_charfield"),
        TranslatableField("test_textfield"),
        TranslatableField("test_emailfield"),
    ]


class InheritedTestModel(TestModel):
    class Meta:
        unique_together = None


class TestChildObject(TranslatableMixin, Orderable):
    page = ParentalKey(TestPage, related_name="test_childobjects")
    field = models.TextField()

    translatable_fields = [TranslatableField("field")]

    class Meta(TranslatableMixin.Meta, Orderable.Meta):
        pass


# TODO: System check for TranslatableMixin here
class TestSynchronizedChildObject(Orderable):
    page = ParentalKey(TestPage, related_name="test_synchronized_childobjects")
    field = models.TextField()

    translatable_fields = [TranslatableField("field")]


# FIXME: Rename me
class TestNonParentalChildObject(TranslatableMixin, Orderable):
    page = models.ForeignKey(
        TestPage, on_delete=models.CASCADE, related_name="test_nonparentalchildobjects"  # FIXME: inconsistent related_name
    )
    field = models.TextField()

    translatable_fields = [TranslatableField("field")]


class TestHomePage(Page):
    pass


class TestGenerateTranslatableFieldsPage(Page):
    """
    A page type that tests the builtin automatic generation of translatable fields.
    """

    test_charfield = models.CharField(max_length=255, blank=True)
    test_charfield_with_choices = models.CharField(max_length=255, blank=True, choices=[('a', "A"), ('b', "B")])
    test_textfield = models.TextField(blank=True)
    test_emailfield = models.EmailField(blank=True)
    test_slugfield = models.SlugField(blank=True)
    test_urlfield = models.URLField(blank=True)

    test_richtextfield = RichTextField(blank=True)
    test_streamfield = StreamField(TestStreamBlock, blank=True)

    test_snippet = models.ForeignKey(
        TestSnippet, null=True, blank=True, on_delete=models.SET_NULL
    )

    test_nontranslatablesnippet = models.ForeignKey(
        NonTranslatableSnippet, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    test_customfield = TestCustomField(blank=True)


class TranslatableChildObject(TranslatableMixin, Orderable):
    page = ParentalKey(TestGenerateTranslatableFieldsPage, related_name="test_translatable_childobjects")
    field = models.TextField()

    class Meta(TranslatableMixin.Meta, Orderable.Meta):
        pass


class NonTranslatableChildObject(Orderable):
    page = ParentalKey(TestGenerateTranslatableFieldsPage, related_name="test_nontranslatable_childobjects")
    field = models.TextField()
