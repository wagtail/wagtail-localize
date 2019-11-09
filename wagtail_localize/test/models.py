from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page, Orderable

from wagtail_localize.fields import TranslatableField
from wagtail_localize.models import TranslatableMixin, TranslatablePageMixin
from wagtail_localize.segments import SegmentValue


class TestSnippet(TranslatableMixin, models.Model):
    field = models.TextField()

    translatable_fields = [TranslatableField("field")]


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
        return [SegmentValue("foo", "{} {}".format(value["field_a"], value["field_b"]))]


class TestStreamBlock(blocks.StreamBlock):
    test_charblock = blocks.CharBlock(max_length=255)
    test_textblock = blocks.TextBlock()
    test_emailblock = blocks.EmailBlock()
    test_urlblock = blocks.URLBlock()
    test_richtextblock = blocks.RichTextBlock()
    test_rawhtmlblock = blocks.RawHTMLBlock()
    test_blockquoteblock = blocks.BlockQuoteBlock()
    test_structblock = TestStructBlock()
    test_listblock = blocks.ListBlock(blocks.TextBlock())
    test_nestedstreamblock = TestNestedStreamBlock()
    test_customstructblock = CustomStructBlock()


class TestCustomField(models.TextField):
    def get_translatable_segments(self, value):
        if not value:
            # Don't disrupt other tests
            return []

        return [SegmentValue("foo", "{} and some extra".format(value))]


class TestPage(TranslatablePageMixin, Page):
    test_charfield = models.CharField(max_length=255, blank=True)
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
    ]


class TestChildObject(TranslatableMixin, Orderable):
    page = ParentalKey(TestPage, related_name="test_childobjects")
    field = models.TextField()

    translatable_fields = [TranslatableField("field")]
