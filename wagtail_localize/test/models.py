from django.db import models
from django.utils.translation import gettext_lazy
from modelcluster.fields import ParentalKey
from wagtail.admin.edit_handlers import (
    FieldPanel,
    InlinePanel,
    ObjectList,
    PageChooserPanel,
    StreamFieldPanel,
    TabbedInterface,
)
from wagtail.core import blocks
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Orderable, Page, TranslatableMixin
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.models import register_snippet

from wagtail_localize.components import register_translation_component
from wagtail_localize.fields import SynchronizedField, TranslatableField
from wagtail_localize.models import TranslationSource
from wagtail_localize.segments import StringSegmentValue


# Telepath added in Wagtail 2.13
try:
    from wagtail.core import telepath
except ImportError:
    telepath = False


@register_snippet
class TestSnippet(TranslatableMixin, models.Model):
    field = models.TextField(gettext_lazy("field"))
    # To test field level validation of snippets
    small_charfield = models.CharField(max_length=10, blank=True)

    translatable_fields = [
        TranslatableField("field"),
        TranslatableField("small_charfield"),
    ]


@register_snippet
class NonTranslatableSnippet(models.Model):
    field = models.TextField()


class TestStructBlock(blocks.StructBlock):
    field_a = blocks.TextBlock()
    field_b = blocks.TextBlock()


class TestNestedStreamBlock(blocks.StreamBlock):
    block_a = blocks.TextBlock()
    block_b = blocks.TextBlock()
    block_l = blocks.ListBlock(blocks.CharBlock())


class TestChooserStructBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock()


class TestNestedChooserStructBlock(blocks.StructBlock):
    nested_page = TestChooserStructBlock()


class CustomStructBlock(blocks.StructBlock):
    field_a = blocks.TextBlock()
    field_b = blocks.TextBlock()

    def get_translatable_segments(self, value):
        return [
            StringSegmentValue(
                "foo", "{} / {}".format(value["field_a"], value["field_b"])
            )
        ]

    def restore_translated_segments(self, value, segments):
        for segment in segments:
            if segment.path == "foo":
                field_a, field_b = segment.render_text().split("/")
                value["field_a"] = field_a.strip()
                value["field_b"] = field_b.strip()

        return value


class CustomBlockWithoutExtractMethod(blocks.Block):
    def render_form(self, *args, **kwargs):
        """Placeholder for Wagtail < 2.13"""
        return ""

    class Meta:
        default = None


class ListStructBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False)
    items = blocks.ListBlock(blocks.CharBlock)


if telepath:

    class CustomBlockWithoutExtractMethodAdapter(telepath.Adapter):
        js_constructor = "CustomBlockWithoutExtractMethod"

        def js_args(self, block):
            return []

    telepath.register(
        CustomBlockWithoutExtractMethodAdapter(), CustomBlockWithoutExtractMethod
    )


class TestStreamBlock(blocks.StreamBlock):
    test_charblock = blocks.CharBlock(max_length=255)
    test_textblock = blocks.TextBlock(label=gettext_lazy("text block"))
    test_emailblock = blocks.EmailBlock()
    test_urlblock = blocks.URLBlock()
    test_richtextblock = blocks.RichTextBlock()
    test_rawhtmlblock = blocks.RawHTMLBlock()
    test_blockquoteblock = blocks.BlockQuoteBlock()
    test_structblock = TestStructBlock()
    test_listblock = blocks.ListBlock(blocks.TextBlock())
    test_listblock_in_structblock = ListStructBlock()
    test_nestedstreamblock = TestNestedStreamBlock()
    test_customstructblock = CustomStructBlock()
    test_customblockwithoutextractmethod = CustomBlockWithoutExtractMethod()
    test_pagechooserblock = blocks.PageChooserBlock()
    test_pagechooserblock_with_restricted_types = blocks.PageChooserBlock(
        ["wagtail_localize_test.TestHomePage", "wagtail_localize_test.TestPage"]
    )
    test_imagechooserblock = ImageChooserBlock()
    test_documentchooserblock = DocumentChooserBlock()
    test_snippetchooserblock = SnippetChooserBlock(TestSnippet)
    test_nontranslatablesnippetchooserblock = SnippetChooserBlock(
        NonTranslatableSnippet
    )
    test_embedblock = EmbedBlock()

    test_chooserstructblock = TestChooserStructBlock()
    test_nestedchooserstructblock = TestNestedChooserStructBlock()


class TestCustomField(models.TextField):
    def get_translatable_segments(self, value):
        if not value:
            # Don't disrupt other tests
            return []

        return [StringSegmentValue("foo", "{} and some extra".format(value))]


class TestPage(Page):
    test_charfield = models.CharField(
        gettext_lazy("char field"), max_length=255, blank=True, null=True, default=""
    )
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
    test_not_overridable_synchronized_textfield = models.TextField(blank=True)
    test_synchronized_emailfield = models.EmailField(blank=True)
    test_synchronized_slugfield = models.SlugField(blank=True)
    test_synchronized_urlfield = models.URLField(blank=True)

    test_synchronized_richtextfield = RichTextField(blank=True)
    test_synchronized_streamfield = StreamField(TestStreamBlock, blank=True)

    test_synchronized_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    test_synchronized_document = models.ForeignKey(
        "wagtaildocs.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    test_synchronized_snippet = models.ForeignKey(
        TestSnippet, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    test_page = models.ForeignKey(
        Page, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    test_page_specific_type = models.ForeignKey(
        "TestHomePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    test_page_with_restricted_types = models.ForeignKey(
        Page, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
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
        SynchronizedField(
            "test_not_overridable_synchronized_textfield", overridable=False
        ),
        SynchronizedField("test_synchronized_emailfield"),
        SynchronizedField("test_synchronized_slugfield"),
        SynchronizedField("test_synchronized_urlfield"),
        SynchronizedField("test_synchronized_richtextfield"),
        SynchronizedField("test_synchronized_streamfield"),
        SynchronizedField("test_synchronized_image"),
        SynchronizedField("test_synchronized_document"),
        SynchronizedField("test_synchronized_snippet"),
        SynchronizedField("test_synchronized_childobjects"),
        SynchronizedField("test_page"),
        SynchronizedField("test_page_specific_type"),
        SynchronizedField("test_page_with_restricted_types"),
        SynchronizedField("test_synchronized_customfield"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("test_charfield"),
        FieldPanel("test_textfield"),
        FieldPanel("test_emailfield"),
        FieldPanel("test_slugfield"),
        FieldPanel("test_urlfield"),
        FieldPanel("test_richtextfield"),
        StreamFieldPanel("test_streamfield"),
        FieldPanel("test_snippet"),
        InlinePanel("test_childobjects"),
        FieldPanel("test_customfield"),
        FieldPanel("test_synchronized_charfield"),
        FieldPanel("test_synchronized_textfield"),
        FieldPanel("test_synchronized_emailfield"),
        FieldPanel("test_synchronized_slugfield"),
        FieldPanel("test_synchronized_urlfield"),
        FieldPanel("test_synchronized_richtextfield"),
        StreamFieldPanel("test_synchronized_streamfield"),
        FieldPanel("test_synchronized_image"),
        FieldPanel("test_synchronized_document"),
        FieldPanel("test_synchronized_snippet"),
        InlinePanel("test_synchronized_childobjects"),
        PageChooserPanel("test_page"),
        PageChooserPanel("test_page_specific_type"),
        PageChooserPanel(
            "test_page_with_restricted_types",
            ["wagtail_localize_test.TestHomePage", "wagtail_localize_test.TestPage"],
        ),
        FieldPanel("test_synchronized_customfield"),
    ]


class TestWithTranslationModeDisabledPage(Page):
    # Always keep the translation mode off, regardless of the global
    # WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE value
    localize_default_translation_mode = "simple"


class TestWithTranslationModeEnabledPage(Page):
    # Always keep the translation mode on, regardless of the global
    # WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE value
    localize_default_translation_mode = "synced"


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
        TestPage,
        on_delete=models.CASCADE,
        related_name="test_nonparentalchildobjects",  # FIXME: inconsistent related_name
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
    test_charfield_with_choices = models.CharField(
        max_length=255, blank=True, choices=[("a", "A"), ("b", "B")]
    )
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
        NonTranslatableSnippet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    test_customfield = TestCustomField(blank=True)


class TestOverrideTranslatableFieldsPage(TestGenerateTranslatableFieldsPage):
    override_translatable_fields = [
        SynchronizedField("test_charfield"),
        TranslatableField("test_emailfield"),
    ]


class TranslatableChildObject(TranslatableMixin, Orderable):
    page = ParentalKey(
        TestGenerateTranslatableFieldsPage,
        related_name="test_translatable_childobjects",
    )
    field = models.TextField()

    class Meta(TranslatableMixin.Meta, Orderable.Meta):
        pass


class NonTranslatableChildObject(Orderable):
    page = ParentalKey(
        TestGenerateTranslatableFieldsPage,
        related_name="test_nontranslatable_childobjects",
    )
    field = models.TextField()


class TestModelWithInvalidForeignKey(TranslatableMixin, models.Model):
    fk = models.ForeignKey("wagtailcore.Site", on_delete=models.CASCADE)

    # This should raise an error as the model being pointed to is not
    # translatable!
    translatable_fields = [
        TranslatableField("fk"),
    ]


class PageWithCustomEditHandler(Page):
    foo_field = models.TextField()
    bar_field = models.TextField()
    baz_field = models.TextField()

    foo_panels = [
        FieldPanel("foo_field"),
    ]

    bar_panels = [
        FieldPanel("bar_field"),
        FieldPanel("baz_field"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(bar_panels, heading="Bar"),
            ObjectList([InlinePanel("child_objects")], heading="Child objects"),
            ObjectList(foo_panels, heading="Foo"),
            ObjectList(Page.content_panels, heading="Content"),
            ObjectList(Page.promote_panels, heading="Promote"),
            ObjectList(Page.settings_panels, heading="Settings"),
        ]
    )


class PageWithCustomEditHandlerChildObject(TranslatableMixin, Orderable):
    page = ParentalKey(PageWithCustomEditHandler, related_name="child_objects")
    field = models.TextField()

    class Meta(TranslatableMixin.Meta, Orderable.Meta):
        pass


@register_translation_component(
    heading="Custom translation view component",
    help_text="This is the component help text",
    enable_text="Add custom data",
    disable_text="Do not send add custom data",
)
class CustomTranslationData(models.Model):
    translation_source = models.ForeignKey(
        TranslationSource, on_delete=models.CASCADE, editable=False
    )
    custom_text_field = models.CharField(max_length=255)

    @classmethod
    def get_or_create_from_source_and_translation_data(
        cls, translation_source, translations, **kwargs
    ):
        custom_data, created = CustomTranslationData.objects.get_or_create(
            translation_source=translation_source, **kwargs
        )

        return custom_data, created


@register_translation_component(
    heading="Notes",
    enable_text="Add notes",
    disable_text="Do not add notes",
)
class CustomButSimpleTranslationData(models.Model):
    notes = models.CharField(max_length=255)
