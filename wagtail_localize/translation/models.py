import json
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.utils.translation import gettext as _
from django.utils import timezone
from django.utils.text import slugify
from modelcluster.models import (
    ClusterableModel,
    get_serializable_data_for_fields,
    model_from_serializable_data,
)
from wagtail.core.models import Page
from wagtail.snippets.models import get_snippet_models
from wagtail.images.models import AbstractImage
from wagtail.documents.models import AbstractDocument

from wagtail_localize.models import ParentNotTranslatedError

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

    def get_for_instance(self, instance):
        return self.get(
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
            translation_key=self.translation_key, locale_id=pk(locale)
        ).exists()

    def get_source_instance(self):
        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, is_source_translation=True
        )

    def get_instance(self, locale):
        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale_id=pk(locale)
        )

    def get_instance_or_none(self, locale):
        try:
            return self.get_instance(locale)
        except self.content_type.model_class().DoesNotExist:
            pass

    class Meta:
        unique_together = [("content_type", "translation_key")]


class SourceDeletedError(Exception):
    pass


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


class TranslationSourceQuerySet(models.QuerySet):
    def get_for_instance(self, instance):
        object = TranslatableObject.objects.get_for_instance(
            instance
        )
        return self.filter(
            object=object,
            locale=instance.locale,
        )


class TranslationSource(models.Model):
    """
    A piece of content that to be used as a source for translations.
    """

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="sources"
    )
    # object.content_type refers to the model that the TranslatableMixin was added to, however that model
    # might have child models. So specific_content_type is needed to refer to the content type that this
    # source data was extracted from.
    specific_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    locale = models.ForeignKey("wagtail_localize.Locale", on_delete=models.CASCADE)
    object_title = models.TextField(max_length=1000, blank=True)
    content_json = models.TextField()
    created_at = models.DateTimeField()

    objects = TranslationSourceQuerySet.as_manager()

    @classmethod
    def from_instance(cls, instance, force=False):
        # Make sure we're using the specific version of pages
        if isinstance(instance, Page):
            instance = instance.specific

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
            previous_revision = object.sources.order_by("created_at").last()
            if previous_revision:
                if json.loads(content_json) == json.loads(
                    previous_revision.content_json
                ):
                    return previous_revision, False

        return (
            cls.objects.create(
                object=object,
                specific_content_type=ContentType.objects.get_for_model(instance.__class__),
                locale=instance.locale,
                object_title=str(instance),
                content_json=content_json,
                created_at=timezone.now(),
            ),
            True,
        )

    def get_source_instance(self):
        """
        This gets the live version of instance that the source data was extracted from.

        This is different to source.object.get_instance(source.locale) as the instance
        returned by this methid will have the same model that the content was extracted
        from. The model returned by `object.get_instance` might be more generic since
        that model only records the model that the TranslatableMixin was applied to but
        that model might have child models.
        """
        return self.specific_content_type.get_object_for_this_type(
            translation_key=self.object_id, locale_id=self.locale_id
        )

    def as_instance(self):
        """
        Builds an instance of the object with the content at this revision.
        """
        try:
            instance = self.get_source_instance()
        except models.ObjectDoesNotExist:
            raise SourceDeletedError

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
                SegmentLocation.from_segment_value(self, self.locale, segment)

    def get_segments(self, with_translation=None, raise_if_missing_translation=True, segment_translation_fallback_to_source=False):
        segment_locations = (
            SegmentLocation.objects.filter(source=self)
            .select_related("context", "segment")
        )

        if with_translation:
            segment_locations = segment_locations.annotate_translation(with_translation)

        template_locations = (
            TemplateLocation.objects.filter(source=self)
            .select_related("template")
            .select_related("context")
        )

        related_object_locations = (
            RelatedObjectLocation.objects.filter(source=self)
            .select_related("object")
            .select_related("context")
        )

        segments = []

        for location in segment_locations:
            if with_translation and not location.translation:
                if segment_translation_fallback_to_source:
                    location.translation = location.segment.text

                elif raise_if_missing_translation:
                    raise MissingTranslationError(location, with_translation)

            # TODO: We need to allow SegmentValues to include both source and translation at the same time
            segment = SegmentValue.from_html(
                location.context.path, location.segment.text
            ).with_order(location.order)
            if location.html_attrs:
                segment.replace_html_attrs(json.loads(location.html_attrs))

            if with_translation and location.translation:
                segment.translation = SegmentValue.from_html(
                    location.context.path, location.translation
                ).with_order(location.order)

                if location.html_attrs:
                    segment.translation.replace_html_attrs(json.loads(location.html_attrs))

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
            if with_translation and not location.object.has_translation(with_translation) and raise_if_missing_translation:
                raise MissingRelatedObjectError(location, with_translation)

            segment = RelatedObjectValue(
                location.context.path,
                location.object.content_type,
                location.object.translation_key,
                order=location.order,
            )
            segments.append(segment)

        return segments

    @transaction.atomic
    def create_or_update_translation(self, locale, user=None, publish=True, segment_translation_fallback_to_source=False):
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
        segments = self.get_segments(with_translation=locale, segment_translation_fallback_to_source=segment_translation_fallback_to_source)

        # Ingest all translated segments
        ingest_segments(original, translation, self.locale, locale, [segment.translation if isinstance(segment, SegmentValue) else segment for segment in segments])

        if isinstance(translation, Page):
            # Make sure the slug is valid
            translation.slug = slugify(translation.slug)
            translation.save()

            # Create a new revision
            page_revision = translation.save_revision(user=user)

            if publish:
                page_revision.publish()
        else:
            translation.save()
            page_revision = None

        # Log that the translation was made
        TranslationLog.objects.create(
            source=self, locale=locale, page_revision=page_revision
        )

        return translation, created


class Translation(models.Model):
    """
    Manages the translation of an object into a locale.

    An instance of this model is created whenever something is submitted for translation
    into a new language. They live until either the source or destination has been deleted.

    Only one of these will exist for a given object/langauge. If the object is resubmitted
    for translation, the existing Translation instance's 'source' field is updated.
    """
    # A unique ID that can be used to reference this request in external systems
    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="translations"
    )
    target_locale = models.ForeignKey(
        "wagtail_localize.Locale",
        on_delete=models.CASCADE,
        related_name="translations",
    )

    # Note: The source may be changed if the object is resubmitted for translation into the same locale
    source = models.ForeignKey(
        TranslationSource, on_delete=models.CASCADE, related_name="translations"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('object', 'target_locale'),
        ]

    def get_progress(self):
        """
        Returns the current progress of translating this Translation.

        Returns two integers:
        - The total number of segments in the source that need to be translated
        - The number of segments that have been translated into the locale
        """
        # Get QuerySet of Segments that need to be translated
        required_segments = SegmentLocation.objects.filter(source_id=self.source_id)

        # Annotate each Segment with a flag that indicates whether the segment is translated
        # into the locale
        required_segments = required_segments.annotate(
            is_translated=Exists(
                SegmentTranslation.objects.filter(
                    translation_of_id=OuterRef("segment_id"),
                    context_id=OuterRef("context_id"),
                    locale_id=self.target_locale_id,
                )
            )
        )

        # Count the total number of segments and the number of translated segments
        aggs = required_segments.annotate(
            is_translated_i=Case(
                When(is_translated=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).aggregate(total_segments=Count("pk"), translated_segments=Sum("is_translated_i"))

        return aggs["total_segments"], aggs["translated_segments"]

    def get_status_display(self):
        """
        Returns a string to describe the current status of this translation to a user.
        """
        total_segments, translated_segments = self.get_progress()
        if total_segments == translated_segments:
            return _("Up to date")
        else:
            # TODO show actual number of strings required?
            return _("Waiting for translations")

    def update(self, user=None):
        try:
            self.source.create_or_update_translation(self.target_locale, user=user, segment_translation_fallback_to_source=True)
        except (ParentNotTranslatedError, MissingRelatedObjectError):
            # TODO: Create missing objects
            pass


class TranslationLog(models.Model):
    """
    This model logs when we make a translation.
    """

    source = models.ForeignKey(
        TranslationSource, on_delete=models.CASCADE, related_name="translation_logs"
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
        return self.source.object.get_instance(self.locale)


class Segment(models.Model):
    UUID_NAMESPACE = uuid.UUID("59ed7d1c-7eb5-45fa-9c8b-7a7057ed56d7")

    locale = models.ForeignKey("wagtail_localize.Locale", on_delete=models.CASCADE)

    text_id = models.UUIDField()
    text = models.TextField()

    @classmethod
    def get_text_id(cls, text):
        return uuid.uuid5(cls.UUID_NAMESPACE, text)

    @classmethod
    def from_text(cls, locale, text):
        segment, created = cls.objects.get_or_create(
            locale_id=pk(locale),
            text_id=cls.get_text_id(text),
            defaults={"text": text},
        )

        return segment

    def save(self, *args, **kwargs):
        if self.text and self.text_id is None:
            self.text_id = self.get_text_id(self.text)

        return super().save(*args, **kwargs)

    class Meta:
        unique_together = [("locale", "text_id")]


class TranslationContext(models.Model):
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
        Looks for the TranslationContext that the given string represents.
        """
        object_id, path = msgctxt.split(":")
        path_id = cls.get_path_id(path)
        return cls.objects.get(object_id=object_id, path_id=path_id)


class SegmentTranslation(models.Model):
    translation_of = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="translations"
    )
    locale = models.ForeignKey("wagtail_localize.Locale", on_delete=models.CASCADE, related_name="segment_translations")
    context = models.ForeignKey(
        TranslationContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="translations",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("locale", "translation_of", "context")]

    @classmethod
    def from_text(cls, translation_of, locale, context, text):
        segment, created = cls.objects.get_or_create(
            translation_of=translation_of,
            locale_id=pk(locale),
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
    source = models.ForeignKey(TranslationSource, on_delete=models.CASCADE)
    context = models.ForeignKey(TranslationContext, on_delete=models.PROTECT,)
    order = models.PositiveIntegerField()

    class Meta:
        abstract = True


class SegmentLocationQuerySet(models.QuerySet):
    def annotate_translation(self, locale):
        """
        Adds a 'translation' field to the segments containing the
        text content of the segment translated into the specified
        locale.
        """
        return self.annotate(
            translation=Subquery(
                SegmentTranslation.objects.filter(
                    translation_of_id=OuterRef("segment_id"),
                    locale_id=pk(locale),
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
    def from_segment_value(cls, source, language, segment_value):
        segment = Segment.from_text(language, segment_value.html_with_ids)
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id, path=segment_value.path,
        )

        segment_loc, created = cls.objects.get_or_create(
            source=source,
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
    def from_template_value(cls, source, template_value):
        template = Template.from_template_value(template_value)
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id, path=template_value.path,
        )

        template_loc, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=template_value.order,
            template=template,
        )

        return template_loc


class RelatedObjectLocationQuerySet(models.QuerySet):
    def annotate_translation_id(self, locale):
        """
        Adds a 'translation_id' field to the segments containing the
        text content of the Translation of the related object
        in the specified locale
        """
        return self.annotate(
            translation_id=Subquery(
                Translation.objects.filter(
                    source__object_id=OuterRef("object_id"),
                    target_locale_id=pk(locale),
                ).values("id")
            )
        )


class RelatedObjectLocation(BaseLocation):
    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="references"
    )

    objects = RelatedObjectLocationQuerySet.as_manager()

    @classmethod
    def from_related_object_value(cls, source, related_object_value):
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id, path=related_object_value.path,
        )

        related_object_loc, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=related_object_value.order,
            object=TranslatableObject.objects.get_or_create(
                content_type=related_object_value.content_type,
                translation_key=related_object_value.translation_key,
            )[0],
        )

        return related_object_loc
