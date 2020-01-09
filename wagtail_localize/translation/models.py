import json
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import Subquery, OuterRef
from django.utils import timezone
from django.utils.text import slugify
from modelcluster.models import (
    ClusterableModel,
    get_serializable_data_for_fields,
    model_from_serializable_data,
)
from wagtail.core.models import Page

from .segments import SegmentValue, TemplateValue, RelatedObjectValue
from .segments.extract import extract_segments
from .segments.ingest import ingest_segments


def pk(obj):
    if isinstance(obj, models.Model):
        return obj.pk
    else:
        return obj


class TranslatableObjectManager(models.Manager):
    def get_or_create_from_instance(self, instance):
        return self.get_or_create(
            translation_key=instance.translation_key,
            content_type=ContentType.objects.get_for_model(
                instance.get_translation_model()
            ),
        )


class TranslatableObject(models.Model):
    """
    Represents something that can be translated.

    Note that one instance of this represents all translations for the object.
    """

    translation_key = models.UUIDField(primary_key=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )

    objects = TranslatableObjectManager()

    def has_translation(self, locale):
        return self.content_type.get_all_objects_for_this_type(
            translation_key=self.translation_key, locale=locale
        ).exists()

    def get_instance(self, locale):
        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale=locale
        )

    class Meta:
        unique_together = [("content_type", "translation_key")]


class MissingTranslationError(Exception):
    def __init__(self, location, locale):
        self.location = location
        self.locale = locale

        super().__init__()


class MissingRelatedObjectError(Exception):
    def __init__(self, location, locale):
        self.location = location
        self.locale = locale

        super().__init__()


class TranslatableRevision(models.Model):
    """
    A piece of content that to be used as a source for translations.
    """

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="revisions"
    )
    locale = models.ForeignKey("wagtail_localize.Locale", on_delete=models.CASCADE)
    content_json = models.TextField()
    created_at = models.DateTimeField()

    page_revision = models.OneToOneField(
        "wagtailcore.PageRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wagtaillocalize_revision",
    )

    @classmethod
    def get_or_create_from_page_revision(cls, page_revision):
        page = page_revision.page.specific

        object, created = TranslatableObject.objects.get_or_create_from_instance(page)

        return TranslatableRevision.objects.get_or_create(
            object=object,
            page_revision=page_revision,
            defaults={
                "locale_id": page.locale_id,
                "content_json": page_revision.content_json,
                "created_at": page_revision.created_at,
            },
        )

    @classmethod
    def from_instance(cls, instance, force=False):
        object, created = TranslatableObject.objects.get_or_create_from_instance(
            instance
        )

        if isinstance(instance, ClusterableModel):
            content_json = instance.to_json()
        else:
            serializable_data = get_serializable_data_for_fields(instance)
            content_json = json.dumps(serializable_data, cls=DjangoJSONEncoder)

        if not force:
            # Check if the instance has changed at all since the previous revision
            previous_revision = object.revisions.order_by("created_at").last()
            if previous_revision:
                if json.loads(content_json) == json.loads(
                    previous_revision.content_json
                ):
                    return previous_revision, False

        return (
            cls.objects.create(
                object=object,
                locale=instance.locale,
                content_json=content_json,
                created_at=timezone.now(),
            ),
            True,
        )

    def as_instance(self):
        """
        Builds an instance of the object with the content at this revision.
        """
        instance = self.object.get_instance(self.locale)

        if isinstance(instance, Page):
            return instance.with_content_json(self.content_json)

        elif isinstance(instance, ClusterableModel):
            new_instance = instance.__class__.from_json(self.content_json)

        else:
            new_instance = model_from_serializable_data(
                instance.__class__, json.loads(self.content_json)
            )

        new_instance.pk = instance.pk
        new_instance.locale = instance.locale
        new_instance.translation_key = instance.translation_key
        new_instance.is_source_translation = instance.is_source_translation

        return new_instance

    def extract_segments(self):
        for segment in extract_segments(self.as_instance()):
            if isinstance(segment, TemplateValue):
                TemplateLocation.from_template_value(self, segment)
            elif isinstance(segment, RelatedObjectValue):
                RelatedObjectLocation.from_related_object_value(self, segment)
            else:
                SegmentLocation.from_segment_value(
                    self, self.locale.language_id, segment
                )

    @transaction.atomic
    def create_or_update_translation(self, locale):
        """
        Creates/updates a translation of the object into the specified locale
        based on the content of this source and the translated strings
        currently in translation memory.
        """
        original = self.as_instance()
        created = False

        try:
            translation = self.object.get_instance(locale)
        except models.ObjectDoesNotExist:
            translation = original.copy_for_translation(locale)
            created = True

        # Copy synchronised fields
        for field in translation.translatable_fields:
            if field.is_synchronized(original):
                setattr(
                    translation, field.field_name, getattr(original, field.field_name)
                )

        # Fetch all translated segments
        segment_locations = (
            SegmentLocation.objects.filter(revision=self)
            .annotate_translation(locale.language)
            .select_related("context")
        )

        template_locations = (
            TemplateLocation.objects.filter(revision=self)
            .select_related("template")
            .select_related("context")
        )

        related_object_locations = (
            RelatedObjectLocation.objects.filter(revision=self)
            .select_related("object")
            .select_related("context")
        )

        segments = []

        for location in segment_locations:
            if not location.translation:
                raise MissingTranslationError(location, locale)

            segment = SegmentValue.from_html(
                location.context.path, location.translation
            ).with_order(location.order)
            if location.html_attrs:
                segment.replace_html_attrs(json.loads(location.html_attrs))

            segments.append(segment)

        for location in template_locations:
            template = location.template
            segment = TemplateValue(
                location.context.path,
                template.template_format,
                template.template,
                template.segment_count,
                order=location.order,
            )
            segments.append(segment)

        for location in related_object_locations:
            if not location.object.has_translation(locale):
                raise MissingRelatedObjectError(location, locale)

            segment = RelatedObjectValue(
                location.context.path,
                location.object.content_type,
                location.object.translation_key,
                order=location.order,
            )
            segments.append(segment)

        # Ingest all translated segments
        ingest_segments(original, translation, self.locale, locale, segments)

        if isinstance(translation, Page):
            # Make sure the slug is valid
            translation.slug = slugify(translation.slug)
            translation.save()

            # Create a new revision
            page_revision = translation.save_revision()
            page_revision.publish()
        else:
            translation.save()
            page_revision = None

        # Log that the translation was made
        TranslationLog.objects.create(
            revision=self, locale=locale, page_revision=page_revision
        )

        return translation, created


class TranslationLog(models.Model):
    """
    This model logs when we make a translation.
    """

    revision = models.ForeignKey(
        TranslatableRevision, on_delete=models.CASCADE, related_name="translation_logs"
    )
    locale = models.ForeignKey(
        "wagtail_localize.Locale",
        on_delete=models.CASCADE,
        related_name="translation_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    page_revision = models.ForeignKey(
        "wagtailcore.PageRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def get_instance(self):
        """
        Gets the instance of the translated object, if it still exists.
        """
        return revision.object.get_instance(self.locale)


class Segment(models.Model):
    UUID_NAMESPACE = uuid.UUID("59ed7d1c-7eb5-45fa-9c8b-7a7057ed56d7")

    language = models.ForeignKey("wagtail_localize.Language", on_delete=models.CASCADE)
    text_id = models.UUIDField()
    text = models.TextField()

    @classmethod
    def get_text_id(cls, text):
        return uuid.uuid5(cls.UUID_NAMESPACE, text)

    @classmethod
    def from_text(cls, language, text):
        segment, created = cls.objects.get_or_create(
            language_id=pk(language),
            text_id=cls.get_text_id(text),
            defaults={"text": text},
        )

        return segment

    def save(self, *args, **kwargs):
        if self.text and self.text_id is None:
            self.text_id = self.get_text_id(self.text)

        return super().save(*args, **kwargs)

    class Meta:
        unique_together = [("language", "text_id")]


class SegmentTranslationContext(models.Model):
    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="+"
    )
    path_id = models.UUIDField()
    path = models.TextField()

    class Meta:
        unique_together = [
            ("object", "path_id"),
        ]

    @classmethod
    def get_path_id(cls, path):
        return uuid.uuid5(uuid.UUID("fcab004a-2b50-11ea-978f-2e728ce88125"), path)

    def save(self, *args, **kwargs):
        if self.path and self.path_id is None:
            self.path_id = self.get_path_id(self.path)

        return super().save(*args, **kwargs)

    def as_string(self):
        """
        Creates a string that can be used in the "msgctxt" field of PO files.
        """
        return str(self.object_id) + ":" + self.path

    @classmethod
    def get_from_string(cls, msgctxt):
        """
        Looks for the SegmentTranslationContext that the given string represents.
        """
        object_id, path = msgctxt.split(":")
        path_id = cls.get_path_id(path)
        return cls.objects.get(object_id=object_id, path_id=path_id)


class SegmentTranslation(models.Model):
    translation_of = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="translations"
    )
    language = models.ForeignKey("wagtail_localize.Language", on_delete=models.CASCADE)
    context = models.ForeignKey(
        SegmentTranslationContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="translations",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("language", "translation_of", "context")]

    @classmethod
    def from_text(cls, translation_of, language, context, text):
        segment, created = cls.objects.get_or_create(
            translation_of=translation_of,
            language_id=pk(language),
            context_id=pk(context),
            defaults={"text": text},
        )

        return segment


class Template(models.Model):
    BASE_UUID_NAMESPACE = uuid.UUID("4599eabc-3f8e-41a9-be61-95417d26a8cd")

    uuid = models.UUIDField(unique=True)
    template = models.TextField()
    template_format = models.CharField(max_length=100)
    segment_count = models.PositiveIntegerField()

    @classmethod
    def from_template_value(cls, template_value):
        uuid_namespace = uuid.uuid5(cls.BASE_UUID_NAMESPACE, template_value.format)

        template, created = cls.objects.get_or_create(
            uuid=uuid.uuid5(uuid_namespace, template_value.template),
            defaults={
                "template": template_value.template,
                "template_format": template_value.format,
                "segment_count": template_value.segment_count,
            },
        )

        return template


class BaseLocation(models.Model):
    revision = models.ForeignKey(TranslatableRevision, on_delete=models.CASCADE)
    context = models.ForeignKey(SegmentTranslationContext, on_delete=models.PROTECT,)
    order = models.PositiveIntegerField()

    class Meta:
        abstract = True


class SegmentLocationQuerySet(models.QuerySet):
    def annotate_translation(self, language):
        """
        Adds a 'translation' field to the segments containing the
        text content of the segment translated into the specified
        language.
        """
        return self.annotate(
            translation=Subquery(
                SegmentTranslation.objects.filter(
                    translation_of_id=OuterRef("segment_id"),
                    language_id=pk(language),
                    context_id=OuterRef("context_id"),
                ).values("text")
            )
        )


class SegmentLocation(BaseLocation):
    segment = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="locations"
    )

    # When we extract the segment, we replace HTML attributes with id tags
    # The attributes that were removed are stored here. These must be
    # added into the translated strings.
    # These are stored as a mapping of element ids to KV mappings of
    # attributes in JSON format. For example:
    #
    #  For this segment: <a id="a1">Link to example.com</a>
    #
    #  The value of this field could be:
    #
    #  {
    #      "a#a1": {
    #          "href": "https://www.example.com"
    #      }
    #  }
    html_attrs = models.TextField(blank=True)

    objects = SegmentLocationQuerySet.as_manager()

    @classmethod
    def from_segment_value(cls, revision, language, segment_value):
        segment = Segment.from_text(language, segment_value.html_with_ids)
        context, context_created = SegmentTranslationContext.objects.get_or_create(
            object_id=revision.object_id, path=segment_value.path,
        )

        segment_loc, created = cls.objects.get_or_create(
            revision=revision,
            context=context,
            order=segment_value.order,
            segment=segment,
            html_attrs=json.dumps(segment_value.get_html_attrs()),
        )

        return segment_loc


class TemplateLocation(BaseLocation):
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="locations"
    )

    @classmethod
    def from_template_value(cls, revision, template_value):
        template = Template.from_template_value(template_value)
        context, context_created = SegmentTranslationContext.objects.get_or_create(
            object_id=revision.object_id, path=template_value.path,
        )

        template_loc, created = cls.objects.get_or_create(
            revision=revision,
            context=context,
            order=template_value.order,
            template=template,
        )

        return template_loc


class RelatedObjectLocation(BaseLocation):
    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="references"
    )

    @classmethod
    def from_related_object_value(cls, revision, related_object_value):
        context, context_created = SegmentTranslationContext.objects.get_or_create(
            object_id=revision.object_id, path=related_object_value.path,
        )

        related_object_loc, created = cls.objects.get_or_create(
            revision=revision,
            context=context,
            order=related_object_value.order,
            object=TranslatableObject.objects.get_or_create(
                content_type=related_object_value.content_type,
                translation_key=related_object_value.translation_key,
            )[0],
        )

        return related_object_loc
