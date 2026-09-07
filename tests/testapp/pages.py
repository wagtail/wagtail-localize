from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail import blocks
from wagtail.admin.panels import (
    FieldPanel,
    InlinePanel,
    ObjectList,
    PageChooserPanel,
    TabbedInterface,
)
from wagtail.blocks import StructBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock

from tests.testapp.models import (
    NonTranslatableSnippet,
    TestCustomField,
    TestSnippet,
    TestStreamBlock,
)
from wagtail_localize.fields import SynchronizedField, TranslatableField


try:
    from wagtail.admin import telepath
except ImportError:  # Wagtail <7.1
    from wagtail import telepath  # noqa: F401

if settings.USE_CUSTOM_PAGE_MODEL:
    from tests.testapp.basepage.models import BasePage as Page
else:
    from wagtail.models import Page

if WAGTAIL_VERSION >= (8, 0):
    import swapper

    PAGE_MODEL_NAME = swapper.get_model_name("wagtailcore", "Page")
else:
    PAGE_MODEL_NAME = "wagtailcore.Page"


if WAGTAIL_VERSION >= (6, 3):
    from wagtail.images.blocks import ImageBlock
else:

    class ImageBlock(StructBlock):
        image = ImageChooserBlock(required=True)
        decorative = blocks.BooleanBlock(
            default=False, required=False, label=gettext_lazy("Image is decorative")
        )
        alt_text = blocks.CharBlock(required=False, label=gettext_lazy("Alt text"))


class TestPageAbstract(models.Model):
    test_charfield = models.CharField(  # noqa: DJ001
        gettext_lazy("char field"), max_length=255, blank=True, null=True, default=""
    )
    test_textfield = models.TextField(blank=True)
    test_emailfield = models.EmailField(blank=True)
    test_slugfield = models.SlugField(blank=True)
    test_urlfield = models.URLField(blank=True)

    test_richtextfield = RichTextField(blank=True)
    test_null_richtextfield = RichTextField(blank=True, null=True)
    test_streamfield = StreamField(TestStreamBlock, blank=True, use_json_field=True)

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
    test_synchronized_streamfield = StreamField(
        TestStreamBlock, blank=True, use_json_field=True
    )

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
        PAGE_MODEL_NAME,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    test_page_specific_type = models.ForeignKey(
        "TestHomePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    test_page_with_restricted_types = models.ForeignKey(
        PAGE_MODEL_NAME,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    test_synchronized_customfield = TestCustomField(blank=True)

    translatable_fields = [
        TranslatableField("test_charfield"),
        TranslatableField("test_textfield"),
        TranslatableField("test_emailfield"),
        TranslatableField("test_slugfield"),
        TranslatableField("test_urlfield"),
        TranslatableField("test_richtextfield"),
        TranslatableField("test_null_richtextfield"),
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

    content_panels = [
        FieldPanel("test_charfield"),
        FieldPanel("test_textfield"),
        FieldPanel("test_emailfield"),
        FieldPanel("test_slugfield"),
        FieldPanel("test_urlfield"),
        FieldPanel("test_richtextfield"),
        FieldPanel("test_streamfield"),
        FieldPanel("test_snippet"),
        InlinePanel("test_childobjects"),
        FieldPanel("test_customfield"),
        FieldPanel("test_synchronized_charfield"),
        FieldPanel("test_synchronized_textfield"),
        FieldPanel("test_synchronized_emailfield"),
        FieldPanel("test_synchronized_slugfield"),
        FieldPanel("test_synchronized_urlfield"),
        FieldPanel("test_synchronized_richtextfield"),
        FieldPanel("test_synchronized_streamfield"),
        FieldPanel("test_synchronized_image"),
        FieldPanel("test_synchronized_document"),
        FieldPanel("test_synchronized_snippet"),
        InlinePanel("test_synchronized_childobjects"),
        PageChooserPanel("test_page"),
        PageChooserPanel("test_page_specific_type"),
        PageChooserPanel(
            "test_page_with_restricted_types",
            ["testpages.TestHomePage", "testpages.TestPage"],
        ),
        FieldPanel("test_synchronized_customfield"),
    ]

    class Meta:
        abstract = True


class TestWithTranslationModeDisabledPageAbstract(models.Model):
    # Always keep the translation mode off, regardless of the global
    # WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE value
    localize_default_translation_mode = "simple"

    class Meta:
        abstract = True


class TestWithTranslationModeEnabledPageAbstract(models.Model):
    # Always keep the translation mode on, regardless of the global
    # WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE value
    localize_default_translation_mode = "synced"

    class Meta:
        abstract = True


class TestHomePageAbstract(models.Model):
    class Meta:
        abstract = True


class TestGenerateTranslatableFieldsPageAbstract(models.Model):
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
    test_streamfield = StreamField(TestStreamBlock, blank=True, use_json_field=True)

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

    class Meta:
        abstract = True


class TestOverrideTranslatableFieldsPageAbstract(models.Model):
    override_translatable_fields = [
        SynchronizedField("test_charfield"),
        TranslatableField("test_emailfield"),
    ]

    class Meta:
        abstract = True


class PageWithCustomEditHandlerAbstract(models.Model):
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

    class Meta:
        abstract = True
