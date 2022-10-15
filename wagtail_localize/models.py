import json
import uuid

import polib

from django.conf import settings
from django.contrib.admin.utils import quote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import (
    Case,
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from modelcluster.fields import ParentalKey
from modelcluster.models import (
    ClusterableModel,
    get_serializable_data_for_fields,
    model_from_serializable_data,
)
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.core import blocks
from wagtail.core.fields import StreamField
from wagtail.core.models import (
    Page,
    PageLogEntry,
    TranslatableMixin,
    _copy,
    get_translatable_models,
)
from wagtail.core.utils import find_available_slug
from wagtail.snippets.models import get_snippet_models

from .compat import DATE_FORMAT, get_revision_model, get_snippet_edit_url
from .fields import copy_synchronised_fields
from .locales.components import LocaleComponentModelForm, register_locale_component
from .segments import (
    OverridableSegmentValue,
    RelatedObjectSegmentValue,
    StringSegmentValue,
    TemplateSegmentValue,
)
from .segments.extract import extract_segments
from .segments.ingest import ingest_segments
from .strings import StringValue, validate_translation_links
from .tasks import background


if WAGTAIL_VERSION >= (2, 16):
    # Only use in a 2.16+ context
    try:
        from wagtail.blocks.list_block import ListValue
    except ImportError:
        from wagtail.core.blocks.list_block import ListValue


def pk(obj):
    """
    A helper that gets the primary key of a model instance if one is passed in.
    If not, this returns the parameter itself.

    This allows functions to have parameters that accept either a primary key
    or model instance. For example:

    ``` python
    def get_translations(target_locale):
        return Translation.objects.filter(target_locale=pk(target_locale))


    # Both of these would be valid calls
    get_translations(Locale.objects.get(id=1))
    get_translations(1)
    ```

    Args:
        obj (Model | any): A model instance or primary key value.

    Returns:
        any: The primary key of the model instance, or value of `obj` parameter.
    """
    if isinstance(obj, models.Model):
        return obj.pk
    else:
        return obj


def get_edit_url(instance):
    """
    Returns the URL of the given instance.

    As there's no standard way to get this information from Wagtail,
    this only works with Pages and snippets at the moment.

    Args:
        instance (Model): A model instance to find the edit URL of.

    Returns:
        str: The URL of the edit page of the given instance.
    """
    if isinstance(instance, Page):
        return reverse("wagtailadmin_pages:edit", args=[instance.id])

    elif instance._meta.model in get_snippet_models():
        return get_snippet_edit_url(instance)

    elif "wagtail_localize.modeladmin" in settings.INSTALLED_APPS:
        return reverse(
            "{app_label}_{model_name}_modeladmin_edit".format(
                app_label=instance._meta.app_label,
                model_name=instance._meta.model_name,
            ),
            args=[quote(instance.pk)],
        )


def get_schema_version(app_label):
    """
    Returns the name of the last applied migration for the given app label.
    """
    migration = (
        MigrationRecorder.Migration.objects.filter(app=app_label)
        .order_by("applied")
        .last()
    )
    if migration:
        return migration.name


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
    A TranslatableObject represents a set of instances of a translatable model
    that are all translations of each another.

    In Wagtail, objects are considered translations of each other when they are
    of the same content type and have the same `translation_key` value.

    Attributes:
        translation_key (UUIDField): The translation_key that value that is used by the instances.
        content_type (ForeignKey to ContentType): Link to the base Django content type representing the model that the
            instances use. Note that this field refers to the model that has the ``locale`` and ``translation_key``
            fields and not the specific type.
    """

    translation_key = models.UUIDField(primary_key=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )

    objects = TranslatableObjectManager()

    def has_translation(self, locale):
        """
        Returns True if there is an instance of this object in the given Locale.

        Args:
            locale (Locale | int): Either a Locale object or an ID of a Locale.

        Returns:
            bool: True if there is an instance of this object in the given locale.
        """
        return self.content_type.get_all_objects_for_this_type(
            translation_key=self.translation_key, locale_id=pk(locale)
        ).exists()

    def get_instance(self, locale):
        """
        Returns a model instance for this object in the given locale.

        Args:
            locale (Locale | int): Either a Locale object or an ID of a Locale.

        Returns:
            Model: The model instance.

        Raises:
            Model.DoesNotExist: If there is not an instance of this object in the given locale.
        """
        return self.content_type.get_object_for_this_type(
            translation_key=self.translation_key, locale_id=pk(locale)
        )

    def get_instance_or_none(self, locale):
        """
        Returns a model instance for this object in the given locale.

        Args:
            locale (Locale | int): Either a Locale object or an ID of a Locale.

        Returns:
            Model: The model instance if one exists.
            None: If the model doesn't exist.
        """
        try:
            return self.get_instance(locale)
        except self.content_type.model_class().DoesNotExist:
            pass

    class Meta:
        unique_together = [("content_type", "translation_key")]


class SourceDeletedError(Exception):
    pass


class CannotSaveDraftError(Exception):
    """
    Raised when a save draft was request on a non-page model.
    """

    pass


class NoViewRestrictionsError(Exception):
    """
    Raised when trying to sync view restrictions for non-Page objects
    """

    pass


class MissingTranslationError(Exception):
    def __init__(self, segment, locale):
        self.segment = segment
        self.locale = locale

        super().__init__()


class MissingRelatedObjectError(Exception):
    def __init__(self, segment, locale):
        self.segment = segment
        self.locale = locale

        super().__init__()


class TranslationSourceQuerySet(models.QuerySet):
    def get_for_instance(self, instance):
        object = TranslatableObject.objects.get_for_instance(instance)
        return self.get(
            object=object,
            locale=instance.locale,
        )

    def get_for_instance_or_none(self, instance):
        try:
            return self.get_for_instance(instance)
        except (TranslationSource.DoesNotExist, TranslatableObject.DoesNotExist):
            return None


class TranslationSource(models.Model):
    """
    Frozen source content that is to be translated.

    This is like a page revision, except it can be created for any model and it's only created/updated when a user
    submits something for translation.

    Attributes:
        object (ForeignKey to TranslatableObject): The object that this is a source for
        specific_content_type (ForeignKey to ContentType): The specific content type that this was extracted from.
            Note that `TranslatableObject.content_type` doesn't store the most specific content type, but this
            does.
        locale (ForeignKey to Locale): The Locale of the instance that this source content was extracted from.
        object_repr (TextField): A string representing the name of the source object. Used in the UI.
        content_json (TextField with JSON contents): The serialized source content. Note that this is serialzed in the
            same way that Wagtail serializes page revisions.
        created_at (DateTimeField): The date/time at which the content was first extracted from this source.
        last_updated_at (DateTimeField): The date/time at which the content was last extracted from this source.
    """

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="sources"
    )
    specific_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    locale = models.ForeignKey("wagtailcore.Locale", on_delete=models.CASCADE)
    object_repr = models.TextField(max_length=200)
    content_json = models.TextField()
    # The name of the last migration to be applied to the app that contains the specific_content_type model
    # This is used to provide a warning to a user when they are editing a translation that was submitted with
    # an older schema
    # Can be blank if the app has no migrations or the TranslationSource was submitted with an old version
    # of Wagtail Localize
    schema_version = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField()

    objects = TranslationSourceQuerySet.as_manager()

    class Meta:
        unique_together = [
            ("object", "locale"),
        ]

    @classmethod
    def get_or_create_from_instance(cls, instance):
        """
        Creates or gets a TranslationSource for the given instance.

        This extracts the content from the given instance. Then stores it in a new TranslationSource instance if one
        doesn't already exist. If one does already exist, it returns the existing TranslationSource without changing
        it.

        Args:
            instance (Model that inherits TranslatableMixin): A Translatable model instance to find a TranslationSource
                instance for.

        Returns:
            tuple[TranslationSource, boolean]: A two-tuple, the first component is the TranslationSource object, and
                the second component is a boolean that is True if the TranslationSource was created.
        """
        # Make sure we're using the specific version of pages
        if isinstance(instance, Page):
            instance = instance.specific

        object, created = TranslatableObject.objects.get_or_create_from_instance(
            instance
        )

        try:
            return (
                TranslationSource.objects.get(
                    object_id=object.translation_key, locale_id=instance.locale_id
                ),
                False,
            )
        except TranslationSource.DoesNotExist:
            pass

        if isinstance(instance, ClusterableModel):
            content_json = instance.to_json()
        else:
            serializable_data = get_serializable_data_for_fields(instance)
            content_json = json.dumps(serializable_data, cls=DjangoJSONEncoder)

        source, created = cls.objects.update_or_create(
            object=object,
            locale=instance.locale,
            # You can't update the content type of a source. So if this happens,
            # it'll try and create a new source and crash (can't have more than
            # one source per object/locale)
            specific_content_type=ContentType.objects.get_for_model(instance.__class__),
            defaults={
                "locale": instance.locale,
                "object_repr": str(instance)[:200],
                "content_json": content_json,
                "schema_version": get_schema_version(instance._meta.app_label) or "",
                "last_updated_at": timezone.now(),
            },
        )
        source.refresh_segments()
        return source, created

    @classmethod
    def update_or_create_from_instance(cls, instance):
        """
        Creates or updates a TranslationSource for the given instance.

        This extracts the content from the given instance. Then stores it in a new TranslationSource instance if one
        doesn't already exist. If one does already exist, it updates the existing TranslationSource.

        Args:
            instance (Model that inherits TranslatableMixin): A Translatable model instance to extract source content
                from.

        Returns:
            tuple[TranslationSource, boolean]: A two-tuple, the first component is the TranslationSource object, and
                the second component is a boolean that is True if the TranslationSource was created.
        """
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

        # Check if the instance has changed since the previous version
        source = TranslationSource.objects.filter(
            object_id=object.translation_key, locale_id=instance.locale_id
        ).first()

        # Check if the instance has changed at all since the previous version
        if source:
            if json.loads(content_json) == json.loads(source.content_json):
                return source, False

        source, created = cls.objects.update_or_create(
            object=object,
            locale=instance.locale,
            # You can't update the content type of a source. So if this happens,
            # it'll try and create a new source and crash (can't have more than
            # one source per object/locale)
            specific_content_type=ContentType.objects.get_for_model(instance.__class__),
            defaults={
                "locale": instance.locale,
                "object_repr": str(instance)[:200],
                "content_json": content_json,
                "schema_version": get_schema_version(instance._meta.app_label) or "",
                "last_updated_at": timezone.now(),
            },
        )
        source.refresh_segments()
        return source, created

    @transaction.atomic
    def update_from_db(self):
        """
        Retrieves the source instance from the database and updates this TranslationSource
        with its current contents.

        Raises:
            Model.DoesNotExist: If the source instance has been deleted.
        """
        instance = self.get_source_instance()

        if isinstance(instance, ClusterableModel):
            self.content_json = instance.to_json()
        else:
            serializable_data = get_serializable_data_for_fields(instance)
            self.content_json = json.dumps(serializable_data, cls=DjangoJSONEncoder)

        self.schema_version = get_schema_version(instance._meta.app_label) or ""
        self.object_repr = str(instance)[:200]
        self.last_updated_at = timezone.now()

        self.save(
            update_fields=[
                "content_json",
                "schema_version",
                "object_repr",
                "last_updated_at",
            ]
        )
        self.refresh_segments()

    def get_source_instance(self):
        """
        This gets the live version of instance that the source data was extracted from.

        This is different to source.object.get_instance(source.locale) as the instance
        returned by this methid will have the same model that the content was extracted
        from. The model returned by `object.get_instance` might be more generic since
        that model only records the model that the TranslatableMixin was applied to but
        that model might have child models.

        Returns:
            Model: The model instance that this TranslationSource was created from.

        Raises:
            Model.DoesNotExist: If the source instance has been deleted.
        """
        return self.specific_content_type.get_object_for_this_type(
            translation_key=self.object_id, locale_id=self.locale_id
        )

    def get_source_instance_edit_url(self):
        """
        Returns the URL to edit the source instance.
        """
        return get_edit_url(self.get_source_instance())

    def get_translated_instance(self, locale):
        return self.specific_content_type.get_object_for_this_type(
            translation_key=self.object_id, locale_id=pk(locale)
        )

    def as_instance(self):
        """
        Builds an instance of the object with the content of this source.

        Returns:
            Model: A model instance that has the content of this TranslationSource.

        Raises:
            SourceDeletedError: if the source instance has been deleted.
        """
        try:
            instance = self.get_source_instance()
        except models.ObjectDoesNotExist:
            raise SourceDeletedError

        if isinstance(instance, Page):
            content_json = self.content_json
            if WAGTAIL_VERSION >= (3, 0):
                # see https://github.com/wagtail/wagtail/pull/8024
                content_json = json.loads(content_json)
            return instance.with_content_json(content_json)

        elif isinstance(instance, ClusterableModel):
            new_instance = instance.__class__.from_json(self.content_json)

        else:
            new_instance = model_from_serializable_data(
                instance.__class__, json.loads(self.content_json)
            )

        new_instance.pk = instance.pk
        new_instance.locale = instance.locale
        new_instance.translation_key = instance.translation_key

        return new_instance

    @transaction.atomic
    def refresh_segments(self):
        """
        Updates the *Segment models to reflect the latest version of the source.

        This is called by `from_instance` so you don't usually need to call this manually.
        """
        seen_string_segment_ids = []
        seen_template_segment_ids = []
        seen_related_object_segment_ids = []
        seen_overridable_segment_ids = []

        instance = self.as_instance()
        for segment in extract_segments(instance):
            if isinstance(segment, TemplateSegmentValue):
                segment_obj = TemplateSegment.from_value(self, segment)
                seen_template_segment_ids.append(segment_obj.id)
            elif isinstance(segment, RelatedObjectSegmentValue):
                segment_obj = RelatedObjectSegment.from_value(self, segment)
                seen_related_object_segment_ids.append(segment_obj.id)
            elif isinstance(segment, OverridableSegmentValue):
                segment_obj = OverridableSegment.from_value(self, segment)
                seen_overridable_segment_ids.append(segment_obj.id)
            else:
                segment_obj = StringSegment.from_value(self, self.locale, segment)
                seen_string_segment_ids.append(segment_obj.id)

            # Make sure the segment's field_path is pre-populated
            segment_obj.context.get_field_path(instance)

        # Delete any segments that weren't mentioned
        self.stringsegment_set.exclude(id__in=seen_string_segment_ids).delete()
        self.templatesegment_set.exclude(id__in=seen_template_segment_ids).delete()
        self.relatedobjectsegment_set.exclude(
            id__in=seen_related_object_segment_ids
        ).delete()
        self.overridablesegment_set.exclude(
            id__in=seen_overridable_segment_ids
        ).delete()

    def export_po(self):
        """
        Exports all translatable strings from this source.

        Note that because there is no target locale, all `msgstr` fields will be blank.

        Returns:
            polib.POFile: A POFile object containing the source translatable strings.
        """
        # Get messages
        messages = []

        for string_segment in (
            StringSegment.objects.filter(source=self)
            .order_by("order")
            .select_related("context", "string")
        ):
            messages.append((string_segment.string.data, string_segment.context.path))

        # Build a PO file
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
        }

        for text, context in messages:
            po.append(
                polib.POEntry(
                    msgid=text,
                    msgctxt=context,
                    msgstr="",
                )
            )

        return po

    def _get_segments_for_translation(self, locale, fallback=False):
        """
        Returns a list of segments that can be passed into "ingest_segments" to translate an object.
        """
        string_segments = (
            StringSegment.objects.filter(source=self)
            .annotate_translation(locale)
            .select_related("context", "string")
        )

        template_segments = (
            TemplateSegment.objects.filter(source=self)
            .select_related("template")
            .select_related("context")
        )

        related_object_segments = (
            RelatedObjectSegment.objects.filter(source=self)
            .select_related("object")
            .select_related("context")
        )

        overridable_segments = (
            OverridableSegment.objects.filter(source=self)
            .annotate_override_json(locale)
            .filter(override_json__isnull=False)
            .select_related("context")
        )

        segments = []

        for string_segment in string_segments:
            if string_segment.translation:
                string = StringValue(string_segment.translation)
            elif fallback:
                string = StringValue(string_segment.string.data)
            else:
                raise MissingTranslationError(string_segment, locale)

            segment_value = StringSegmentValue(
                string_segment.context.path,
                string,
                attrs=json.loads(string_segment.attrs),
            ).with_order(string_segment.order)

            segments.append(segment_value)

        for template_segment in template_segments:
            template = template_segment.template
            segment_value = TemplateSegmentValue(
                template_segment.context.path,
                template.template_format,
                template.template,
                template.string_count,
                order=template_segment.order,
            )
            segments.append(segment_value)

        for related_object_segment in related_object_segments:
            if related_object_segment.object.has_translation(locale):
                segment_value = RelatedObjectSegmentValue(
                    related_object_segment.context.path,
                    related_object_segment.object.content_type,
                    related_object_segment.object.translation_key,
                    order=related_object_segment.order,
                )
                segments.append(segment_value)

            elif fallback:
                # Skip this segment, this will reuse what is already in the database
                continue
            else:
                raise MissingRelatedObjectError(related_object_segment, locale)

        for overridable_segment in overridable_segments:
            segment_value = OverridableSegmentValue(
                overridable_segment.context.path,
                json.loads(overridable_segment.override_json),
                order=overridable_segment.order,
            )
            segments.append(segment_value)

        return segments

    def create_or_update_translation(
        self, locale, user=None, publish=True, copy_parent_pages=False, fallback=False
    ):
        """
        Creates/updates a translation of the object into the specified locale
        based on the content of this source and the translated strings
        currently in translation memory.

        Args:
            locale (Locale): The target locale to generate the translation for.
            user (User, optional): The user who is carrying out this operation. For logging purposes
            publish (boolean, optional): Set this to False to save a draft of the translation. Pages only.
            copy_parent_pages (boolean, optional): Set this to True to make copies of the parent pages if they are not
                yet translated.
            fallback (boolean, optional): Set this to True to fallback to source strings/related objects if they are
                not yet translated. By default, this will raise an error if anything is missing.

        Raises:
            SourceDeletedError: if the source object has been deleted.
            CannotSaveDraftError: if the `publish` parameter was set to `False` when translating a non-page object.
            MissingTranslationError: if a translation is missing and `fallback `is not `True`.
            MissingRelatedObjectError: if a related object is not translated and `fallback `is not `True`.

        Returns:
            Model: The translated instance.
        """
        original = self.as_instance()
        created = False

        # Only pages can be saved as draft
        if not publish and not isinstance(original, Page):
            raise CannotSaveDraftError

        try:
            translation = self.get_translated_instance(locale)
        except models.ObjectDoesNotExist:
            if isinstance(original, Page):
                translation = original.copy_for_translation(
                    locale, copy_parents=copy_parent_pages
                )
            else:
                translation = original.copy_for_translation(locale)

            created = True

        copy_synchronised_fields(original, translation)

        segments = self._get_segments_for_translation(locale, fallback=fallback)

        try:
            with transaction.atomic():
                # Ingest all translated segments
                ingest_segments(original, translation, self.locale, locale, segments)

                if isinstance(translation, Page):
                    # If the page is an alias, convert it into a regular page
                    if translation.alias_of_id:
                        translation.alias_of_id = None
                        translation.save(update_fields=["alias_of_id"], clean=False)

                        # Create initial revision
                        revision = translation.save_revision(
                            user=user, changed=False, clean=False
                        )

                        # Log the alias conversion
                        PageLogEntry.objects.log_action(
                            instance=translation,
                            revision=revision,
                            action="wagtail.convert_alias",
                            user=user,
                            data={
                                "page": {
                                    "id": translation.id,
                                    "title": translation.get_admin_display_title(),
                                },
                            },
                        )

                    # Make sure the slug is valid
                    translation.slug = find_available_slug(
                        translation.get_parent(),
                        slugify(translation.slug),
                        ignore_page_id=translation.id,
                    )
                    translation.save()

                    # Create a new revision
                    page_revision = translation.save_revision(user=user)

                    self.sync_view_restrictions(original, translation)

                    if publish:
                        page_revision.publish()

                else:
                    # Note: we don't need to run full_clean for Pages as Wagtail does that in Page.save()
                    translation.full_clean()

                    translation.save()
                    page_revision = None

        except ValidationError as e:
            # If the validation error's field matches the context of a translation,
            # set that error message on that translation.
            # TODO (someday): Add support for errors raised from streamfield
            for field_name, errors in e.error_dict.items():
                try:
                    context = TranslationContext.objects.get(
                        object=self.object, path=field_name
                    )

                except TranslationContext.DoesNotExist:
                    # TODO (someday): How would we handle validation errors for non-translatable fields?
                    continue

                # Check for string translation
                try:
                    string_translation = StringTranslation.objects.get(
                        translation_of_id__in=StringSegment.objects.filter(
                            source=self
                        ).values_list("string_id", flat=True),
                        context=context,
                        locale=locale,
                    )

                    string_translation.set_field_error(errors)

                except StringTranslation.DoesNotExist:
                    pass

                # Check for segment override
                try:
                    segment_override = SegmentOverride.objects.get(
                        context=context,
                        locale=locale,
                    )

                    segment_override.set_field_error(errors)

                except SegmentOverride.DoesNotExist:
                    pass

            raise

        # Log that the translation was made
        TranslationLog.objects.create(
            source=self, locale=locale, page_revision=page_revision
        )

        return translation, created

    def get_ephemeral_translated_instance(self, locale, fallback=False):
        """
        Returns an instance with the translations added which is not intended to be saved.

        This is used for previewing pages with draft translations applied.

        Args:
            locale (Locale): The target locale to generate the ephemeral translation for.
            fallback (boolean): Set this to True to fallback to source strings/related objects if they are not yet
                translated. By default, this will raise an error if anything is missing.

        Raises:
            SourceDeletedError: if the source object has been deleted.
            MissingTranslationError: if a translation is missing and `fallback `is not `True`.
            MissingRelatedObjectError: if a related object is not translated and `fallback `is not `True`.

        Returns:
            Model: The translated instance with unsaved changes.
        """
        original = self.as_instance()
        translation = self.get_translated_instance(locale)

        copy_synchronised_fields(original, translation)

        segments = self._get_segments_for_translation(locale, fallback=fallback)

        # Ingest all translated segments
        ingest_segments(original, translation, self.locale, locale, segments)

        return translation

    def schema_out_of_date(self):
        """
        Returns True if the app that contains the model this source was generated from
        has been updated since the source was last updated.
        """
        if not self.schema_version:
            return False

        current_schema_version = get_schema_version(
            self.specific_content_type.app_label
        )
        return self.schema_version != current_schema_version

    def sync_view_restrictions(self, original, translation_page):
        """
        Synchronizes view restriction object for the translated page

        Args:
            original (Page|Snippet): The original instance.
            translation_page (Page|Snippet): The translated instance.
        """
        if not isinstance(original, Page) or not isinstance(translation_page, Page):
            raise NoViewRestrictionsError

        if original.view_restrictions.exists():
            original_restriction = original.view_restrictions.first()
            if not translation_page.view_restrictions.exists():
                view_restriction, child_object_map = _copy(
                    original_restriction,
                    exclude_fields=["id"],
                    update_attrs={"page": translation_page},
                )
                view_restriction.save()
            else:
                # if both exist, sync them
                translation_restriction = translation_page.view_restrictions.first()
                should_save = False
                if (
                    translation_restriction.restriction_type
                    != original_restriction.restriction_type
                ):
                    translation_restriction.restriction_type = (
                        original_restriction.restriction_type
                    )
                    should_save = True
                if translation_restriction.password != original_restriction.password:
                    translation_restriction.password = original_restriction.password
                    should_save = True
                if list(
                    original_restriction.groups.values_list("pk", flat=True)
                ) != list(translation_restriction.groups.values_list("pk", flat=True)):
                    translation_restriction.groups.set(
                        original_restriction.groups.all()
                    )

                if should_save:
                    translation_restriction.save()

        elif translation_page.view_restrictions.exists():
            # the original no longer has the restriction, so drop it
            translation_page.view_restrictions.all().delete()

    def update_target_view_restrictions(self, locale):
        """
        Creates a corresponding view restriction object for the translated page for the given locale

        Args:
            locale (Locale): The target locale
        """
        original = self.as_instance()

        # Only update restrictions for pages
        if not isinstance(original, Page):
            return

        try:
            translation_page = self.get_translated_instance(locale)
        except Page.DoesNotExist:
            return

        self.sync_view_restrictions(original, translation_page)


class POImportWarning:
    """
    Base class for warnings that are yielded by Translation.import_po.
    """

    pass


class UnknownString(POImportWarning):
    def __init__(self, index, string):
        self.index = index
        self.string = string

    def __eq__(self, other):
        return (
            isinstance(other, UnknownString)
            and self.index == other.index
            and self.string == other.string
        )

    def __repr__(self):
        return f"<UnknownString {self.index} '{self.string}'>"


class UnknownContext(POImportWarning):
    def __init__(self, index, context):
        self.index = index
        self.context = context

    def __eq__(self, other):
        return (
            isinstance(other, UnknownContext)
            and self.index == other.index
            and self.context == other.context
        )

    def __repr__(self):
        return f"<UnknownContext {self.index} '{self.context}'>"


class StringNotUsedInContext(POImportWarning):
    def __init__(self, index, string, context):
        self.index = index
        self.string = string
        self.context = context

    def __eq__(self, other):
        return (
            isinstance(other, StringNotUsedInContext)
            and self.index == other.index
            and self.string == other.string
            and self.context == other.context
        )

    def __repr__(self):
        return f"<StringNotUsedInContext {self.index} '{self.string}' '{self.context}'>"


class Translation(models.Model):
    """
    Manages the translation of an object into a locale.

    An instance of this model is created whenever an object is submitted for translation into a new language.

    They can be disabled at any time, and are deleted or disabled automatically if either the source or
    destination object is deleted.

    If the translation of a page is disabled, the page editor of the translation would return to the normal Wagtail
    editor.

    Attributes:
        uuid (UUIDField): A unique ID for this translation used for referencing it from external systems.
        source (ForeignKey to TranslationSource): The source that is being translated.
        target_locale (ForeignKey to Locale): The Locale that the source is being translated into.
        created_at (DateTimeField): The date/time the translation was started.
        translations_last_updated_at (DateTimeField): The date/time of when a translated string was last updated.
        destination_last_updated_at (DateTimeField): The date/time of when the destination object was last updated.
        enabled (boolean): Whether this translation is enabled or not.
    """

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    source = models.ForeignKey(
        TranslationSource, on_delete=models.CASCADE, related_name="translations"
    )
    target_locale = models.ForeignKey(
        "wagtailcore.Locale",
        on_delete=models.CASCADE,
        related_name="translations",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    translations_last_updated_at = models.DateTimeField(null=True)
    destination_last_updated_at = models.DateTimeField(null=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ("source", "target_locale"),
        ]

    def get_target_instance(self):
        """
        Fetches the translated instance from the database.

        Raises:
            Model.DoesNotExist: if the translation does not exist.

        Returns:
            Model: The translated instance.
        """
        return self.source.get_translated_instance(self.target_locale)

    def get_target_instance_edit_url(self):
        """
        Returns the URL to edit the target instance.

        Raises:
            Model.DoesNotExist: if the translation does not exist.

        Returns:
            str: The URL of the edit view of the target instance.
        """
        return get_edit_url(self.get_target_instance())

    def get_progress(self):
        """
        Gets the current translation progress.

        Returns
            tuple[int, int]: A two-tuple of integers. First integer is the total number of string segments to be translated.
                The second integer is the number of string segments that have been translated so far.
        """
        # Get QuerySet of Segments that need to be translated
        required_segments = StringSegment.objects.filter(source_id=self.source_id)

        # Annotate each Segment with a flag that indicates whether the segment is translated
        # into the locale
        required_segments = required_segments.annotate(
            is_translated=Exists(
                StringTranslation.objects.filter(
                    translation_of_id=OuterRef("string_id"),
                    context_id=OuterRef("context_id"),
                    locale_id=self.target_locale_id,
                    has_error=False,
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
        ).aggregate(
            total_segments=Count("pk"), translated_segments=Sum("is_translated_i")
        )

        return aggs["total_segments"], aggs["translated_segments"]

    def get_status_display(self):
        """
        Returns a string to describe the current status of this translation to a user.

        Returns:
            str: The status of this translation
        """
        total_segments, translated_segments = self.get_progress()
        if total_segments == translated_segments:
            return _("Up to date")
        else:
            return _("Waiting for translations")

    def export_po(self):
        """
        Exports all translatable strings with any translations that have already been made.

        Returns:
            polib.POFile: A POFile object containing the source translatable strings and any translations.
        """
        # Get messages
        messages = []

        string_segments = (
            StringSegment.objects.filter(source=self.source)
            .order_by("order")
            .select_related("context", "string")
            .annotate_translation(self.target_locale, include_errors=True)
        )

        for string_segment in string_segments:
            messages.append(
                (
                    string_segment.string.data,
                    string_segment.context.path,
                    string_segment.translation,
                )
            )

        # Build a PO file
        po = polib.POFile(wrapwidth=200)
        po.metadata = {
            "POT-Creation-Date": str(timezone.now()),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "X-WagtailLocalize-TranslationID": str(self.uuid),
        }

        for text, context, translation in messages:
            po.append(
                polib.POEntry(
                    msgid=text,
                    msgctxt=context,
                    msgstr=translation or "",
                )
            )

        # Add any obsolete segments that have translations for future reference
        # We find this by looking for obsolete contexts and annotate the latest
        # translation for each one. Contexts that were never translated are
        # excluded
        for translation in (
            StringTranslation.objects.filter(
                context__object_id=self.source.object_id, locale=self.target_locale
            )
            .exclude(
                translation_of_id__in=StringSegment.objects.filter(
                    source=self.source
                ).values_list("string_id", flat=True)
            )
            .select_related("translation_of", "context")
            .iterator()
        ):
            po.append(
                polib.POEntry(
                    msgid=translation.translation_of.data,
                    msgstr=translation.data or "",
                    msgctxt=translation.context.path,
                    obsolete=True,
                )
            )

        return po

    @transaction.atomic
    def import_po(
        self, po, delete=False, user=None, translation_type="manual", tool_name=""
    ):
        """
        Imports all translatable strings with any translations that have already been made.

        Args:
            po (polib.POFile): A POFile object containing the source translatable strings and any translations.
            delete (boolean, optional): Set to True to delete any translations that do not appear in the PO file.
            user (User, optional): The user who is performing this operation. Used for logging purposes.
            translation_type ('manual' or 'machine', optional): Whether the translationw as performed by a human or machine. Defaults to 'manual'.
            tool_name (string, optional): The name of the tool that was used to perform the translation. Defaults to ''.

        Returns:
            list[POImportWarning]: A list of POImportWarning objects representing any non-fatal issues that were
            encountered while importing the PO file.
        """
        seen_translation_ids = set()
        warnings = []

        if "X-WagtailLocalize-TranslationID" in po.metadata and po.metadata[
            "X-WagtailLocalize-TranslationID"
        ] != str(self.uuid):
            return []

        for index, entry in enumerate(po):
            try:
                string = String.objects.get(
                    locale_id=self.source.locale_id, data=entry.msgid
                )
                context = TranslationContext.objects.get(
                    object_id=self.source.object_id, path=entry.msgctxt
                )

                # Ignore blank strings
                if not entry.msgstr:
                    continue

                # Ignore if the string doesn't appear in this context, and if there is not an obsolete StringTranslation
                if (
                    not StringSegment.objects.filter(
                        string=string, context=context
                    ).exists()
                    and not StringTranslation.objects.filter(
                        translation_of=string, context=context
                    ).exists()
                ):
                    warnings.append(
                        StringNotUsedInContext(index, entry.msgid, entry.msgctxt)
                    )
                    continue

                string_translation, created = string.translations.get_or_create(
                    locale_id=self.target_locale_id,
                    context=context,
                    defaults={
                        "data": entry.msgstr,
                        "updated_at": timezone.now(),
                        "translation_type": translation_type,
                        "tool_name": tool_name,
                        "last_translated_by": user,
                        "has_error": False,
                        "field_error": "",
                    },
                )

                seen_translation_ids.add(string_translation.id)

                if not created:
                    # Update the string_translation only if it has changed
                    if string_translation.data != entry.msgstr:
                        string_translation.data = entry.msgstr
                        string_translation.translation_type = translation_type
                        string_translation.tool_name = tool_name
                        string_translation.last_translated_by = user
                        string_translation.updated_at = timezone.now()
                        string_translation.has_error = False  # reset the error flag.
                        string_translation.save()

            except TranslationContext.DoesNotExist:
                warnings.append(UnknownContext(index, entry.msgctxt))

            except String.DoesNotExist:
                warnings.append(UnknownString(index, entry.msgid))

        # Delete any translations that weren't mentioned
        if delete:
            StringTranslation.objects.filter(
                context__object_id=self.source.object_id, locale=self.target_locale
            ).exclude(id__in=seen_translation_ids).delete()

        return warnings

    def save_target(self, user=None, publish=True):
        """
        Saves the target page/snippet using the current translations.

        Args:
            user (User, optional): The user that is performing this action. Used for logging purposes.
            publish (boolean, optional): Set this to False to save a draft of the translation. Pages only.

        Raises:
            SourceDeletedError: if the source object has been deleted.
            CannotSaveDraftError: if the `publish` parameter was set to `False` when translating a non-page object.
            MissingTranslationError: if a translation is missing and `fallback `is not `True`.
            MissingRelatedObjectError: if a related object is not translated and `fallback `is not `True`.

        Returns:
            Model: The translated instance.
        """
        self.source.create_or_update_translation(
            self.target_locale,
            user=user,
            publish=publish,
            fallback=True,
            copy_parent_pages=True,
        )


class TranslationLog(models.Model):
    """
    Keeps Track of when translations are created/updated.

    Attributes:
        source (ForeignKey to TranslationSource): The source that was used for translation.
        locale (ForeignKey to Locale): The Locale that the source was translated into.
        created_at (DateTimeField): The date/time the translation was done.
        page_revision (ForeignKey to PageRevision): If the translation was of a page, this links to the PageRevision
            that was created
    """

    source = models.ForeignKey(
        TranslationSource, on_delete=models.CASCADE, related_name="translation_logs"
    )
    locale = models.ForeignKey(
        "wagtailcore.Locale",
        on_delete=models.CASCADE,
        related_name="translation_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    page_revision = models.ForeignKey(
        get_revision_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def get_instance(self):
        """
        Gets the instance of the translated object, if it still exists.

        Raises:
            Model.DoesNotExist: if the translated object no longer exists.

        Returns:
            The translated object.
        """
        return self.source.object.get_instance(self.locale)


class String(models.Model):
    """
    Represents a unique string of translatable text.

    Attributes:
        locale (ForeignKey to Locale): The locale of the string.
        data (TextField): The string.
        data_hash (UUIDField): A hash of the string, for more efficient indexing of long strings.
    """

    UUID_NAMESPACE = uuid.UUID("59ed7d1c-7eb5-45fa-9c8b-7a7057ed56d7")

    locale = models.ForeignKey(
        "wagtailcore.Locale", on_delete=models.CASCADE, related_name="source_strings"
    )

    data_hash = models.UUIDField()
    data = models.TextField()

    @classmethod
    def _get_data_hash(cls, data):
        """
        Generates a UUID from the given string.

        Args:
            data (string): The string to generate a hash of.

        Returns:
            UUID: The UUID hash.
        """
        return uuid.uuid5(cls.UUID_NAMESPACE, data)

    @classmethod
    def from_value(cls, locale, stringvalue):
        """
        Gets or creates a String instance from a StringValue object.

        Args:
            locale (ForeignKey to Locale) The locale of the string.
            stringvalue (StringValue): The value of the string.

        Returns:
            String: The String instance that corresponds with the given stringvalue and locale.
        """
        string, created = cls.objects.get_or_create(
            locale_id=pk(locale),
            data_hash=cls._get_data_hash(stringvalue.data),
            defaults={"data": stringvalue.data},
        )

        return string

    def as_value(self):
        """
        Creates a StringValue object from the contents of this string.

        Returns:
            StringValue: A StringValue instance with the content of this String.
        """
        return StringValue(self.data)

    def save(self, *args, **kwargs):
        if self.data and self.data_hash is None:
            self.data_hash = self._get_data_hash(self.data)

        return super().save(*args, **kwargs)

    class Meta:
        unique_together = [("locale", "data_hash")]


class TranslationContext(models.Model):
    """
    Represents a context that a string may be translated in.

    Strings can be translated differently in different contexts. A context is a combination of an object and content
    path.

    Attributes:
        object (ForeignKey to TranslatableObject): The object.
        path (TextField): The content path.
        field_path (TextField): the field path.
        path_id (UUIDField): A hash of the path for efficient indexing of long content paths.
    """

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="+"
    )
    path_id = models.UUIDField()
    path = models.TextField()
    field_path = models.TextField()

    class Meta:
        unique_together = [
            ("object", "path_id"),
        ]

    @classmethod
    def _get_path_id(cls, path):
        """
        Generates a UUID from the given content path.

        Args:
            path (string): The content path to generate a hash of.

        Returns:
            UUID: The UUID hash.
        """
        return uuid.uuid5(uuid.UUID("fcab004a-2b50-11ea-978f-2e728ce88125"), path)

    def save(self, *args, **kwargs):
        if self.path and self.path_id is None:
            self.path_id = self._get_path_id(self.path)

        return super().save(*args, **kwargs)

    def get_field_path(self, instance):
        """
        Gets the field path for this context

        Field path's were introduced in version 1.0, any contexts that were created before that release won't have one.
        """
        if not self.field_path:

            def get_field_path_from_field(instance, path_components):
                field_name = path_components[0]
                field = instance._meta.get_field(field_name)

                if isinstance(field, StreamField):

                    def get_field_path_from_streamfield_block(value, path_components):
                        if isinstance(value, blocks.StructValue):
                            blocks_by_id = dict(value)
                        else:
                            if WAGTAIL_VERSION >= (2, 16) and isinstance(
                                value, ListValue
                            ):
                                blocks_by_id = {
                                    block.id: block for block in value.bound_blocks
                                }
                            else:
                                blocks_by_id = {block.id: block for block in value}
                        block_id = path_components[0]
                        block = blocks_by_id[block_id]

                        if isinstance(value, blocks.StructValue):
                            block_type = block_id
                            block_def = value.block.child_blocks[block_type]
                            block_value = block
                        else:
                            if WAGTAIL_VERSION >= (2, 16) and isinstance(
                                value, ListValue
                            ):
                                block_type = "item"
                                block_def = value.list_block.child_block
                            else:
                                block_type = block.block_type
                                block_def = value.stream_block.child_blocks[block_type]
                            block_value = block.value

                        if isinstance(block_def, blocks.StructBlock):
                            return [block_type] + get_field_path_from_streamfield_block(
                                block_value, path_components[1:]
                            )

                        elif isinstance(block_def, blocks.StreamBlock):
                            return [block_type] + get_field_path_from_streamfield_block(
                                block_value, path_components[1:]
                            )
                        elif isinstance(
                            block_def, blocks.ListBlock
                        ) and WAGTAIL_VERSION >= (2, 16):
                            return [block_type] + get_field_path_from_streamfield_block(
                                block_value, path_components[1:]
                            )

                        else:
                            return [block_type]

                    return [field_name] + get_field_path_from_streamfield_block(
                        field.value_from_object(instance), path_components[1:]
                    )

                elif (
                    isinstance(field, models.ManyToOneRel)
                    and isinstance(field.remote_field, ParentalKey)
                    and issubclass(field.related_model, TranslatableMixin)
                ):
                    manager = getattr(instance, field_name)
                    child_instance = manager.get(translation_key=path_components[1])
                    return [field_name] + get_field_path_from_field(
                        child_instance, path_components[2:]
                    )

                else:
                    return [field_name]

            self.field_path = ".".join(
                get_field_path_from_field(instance, self.path.split("."))
            )
            self.save(update_fields=["field_path"])

        return self.field_path


class StringTranslation(models.Model):
    """
    Represents a translation of a string.

    Attributes:
        translation_of (ForeignKey to String): The String that this is a translation of.
        locale (ForeignKey to Locale): The Locale of this translation.
        context (ForeignKey to TranslationContext): The context that this translation was made in. This allows different
            fields/pages to have different translations of the same source string.
        data (TextField): The translation.
        translation_type (CharField with choices 'manual' or 'machine'): Whether the translationw as performed by a human or machine.
        tool_name (CharField): The name of the tool that was used to make this translation.
        last_translated_by (ForeignKey to User): The user who last updated this translation.
        created_at (DateTimeField): The date/time that this translation was first created.
        updated_at (DateFimeField): The date/time that this translation was last updated.
        has_error (BooleanField): Set to True if the value of this translation has an error. We store translations with
            errors in case they were edited from an external system. This allows us to display the error in Wagtail.
        field_error (TextField): If there was a database-level validation error while saving the translated object, that
            error is tored here. Note that this only makes sense if the context is not null.
    """

    TRANSLATION_TYPE_MANUAL = "manual"
    TRANSLATION_TYPE_MACHINE = "machine"
    TRANSLATION_TYPE_CHOICES = [
        (TRANSLATION_TYPE_MANUAL, gettext_lazy("Manual")),
        (TRANSLATION_TYPE_MACHINE, gettext_lazy("Machine")),
    ]

    translation_of = models.ForeignKey(
        String, on_delete=models.CASCADE, related_name="translations"
    )
    locale = models.ForeignKey(
        "wagtailcore.Locale",
        on_delete=models.CASCADE,
        related_name="string_translations",
    )
    context = models.ForeignKey(
        TranslationContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="translations",
    )
    data = models.TextField()
    translation_type = models.CharField(max_length=20, choices=TRANSLATION_TYPE_CHOICES)
    tool_name = models.CharField(max_length=255, blank=True)
    last_translated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    has_error = models.BooleanField(default=False)
    field_error = models.TextField(blank=True)

    class Meta:
        unique_together = [("locale", "translation_of", "context")]

    @classmethod
    def from_text(cls, translation_of, locale, context, data):
        """
        Gets or creates a StringTranslation instance from the given parameters.

        Args:
            translation_of (ForeignKey to String): The String that this is a translation of.
            locale (ForeignKey to Locale): The Locale of this translation.
            context (ForeignKey to TranslationContext): The context that this translation was made in. This allows different
                fields/pages to have different translations of the same source string.
            data (TextField): The translation.

        Returns:
            String: The String instance that corresponds with the given stringvalue and locale.
        """
        segment, created = cls.objects.get_or_create(
            translation_of=translation_of,
            locale_id=pk(locale),
            context_id=pk(context),
            defaults={"data": data},
        )

        return segment

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        super().save(*args, **kwargs)

        # Set has_error if the string is invalid.
        # Since we allow translations to be made by external tools, we need to allow invalid
        # HTML in the database so that it can be fixed in Wagtail. However, we do want to know
        # if any strings are invalid so we don't use them on a page.
        updating_data = update_fields is None or "data" in update_fields
        if updating_data and not self.has_error:

            try:
                StringValue.from_translated_html(self.data)
                validate_translation_links(self.translation_of.data, self.data)
            except ValueError:
                self.has_error = True
                self.save(update_fields=["has_error"])

    def set_field_error(self, error):
        """
        This sets the `has_error`/`field_error` fields to the value of the given ValidationError instance.

        Note: If the given ValidationError contains multiple errors, only the first one is stored.

        Note: This updates the database instance as well.

        Args:
            error (ValidationError): The validation error to store.
        """
        self.has_error = True
        # TODO (someday): We currently only support one error at a time
        self.field_error = error[0].messages[0]
        self.save(update_fields=["has_error", "field_error"])

    def get_error(self):
        """
        Returns a string containing any validation errors on the saved value.

        Returns:
            str: The validation error if there is one.
            None: If there isn't an error.
        """
        if not self.has_error:
            return

        # Check for HTML validation errors
        try:
            StringValue.from_translated_html(self.data)
            validate_translation_links(self.translation_of.data, self.data)
        except ValueError as e:
            return e.args[0]

        # Check if a database error was raised when we last attempted to publish
        if self.context is not None and self.field_error:
            return self.field_error

    def get_comment(self):
        """
        Returns a comment to display to the user containing info on how and when the string was translated.

        Returns:
            str: A comment to display to the user.
        """
        if self.tool_name:
            return _("Translated with {tool_name} on {date}").format(
                tool_name=self.tool_name, date=self.updated_at.strftime(DATE_FORMAT)
            )

        elif self.translation_type == self.TRANSLATION_TYPE_MANUAL:
            return _("Translated manually on {date}").format(
                date=self.updated_at.strftime(DATE_FORMAT)
            )

        elif self.translation_type == self.TRANSLATION_TYPE_MACHINE:
            return _("Machine translated on {date}").format(
                date=self.updated_at.strftime(DATE_FORMAT)
            )


@receiver(post_save, sender=StringTranslation)
def post_save_string_translation(instance, **kwargs):
    # If the StringTranslation is for a page title, update that page's draft_title field
    if instance.context.path == "title":
        # Note: if this StringTranslation isn't for a page, this should do nothing
        Page.objects.filter(
            translation_key=instance.context.object_id, locale_id=instance.locale_id
        ).update(draft_title=instance.data)


@receiver(post_delete, sender=StringTranslation)
def post_delete_string_translation(instance, **kwargs):
    # If the StringTranslation is for a page title, reset that page's draft title to the main title
    if instance.context.path == "title":
        # Note: if this StringTranslation isn't for a page, this should do nothing
        Page.objects.filter(
            translation_key=instance.context.object_id, locale_id=instance.locale_id
        ).update(draft_title=F("title"))


class Template(models.Model):
    """
    A Template stores the structure of a RichTextField or RichTextBlock.

    When a RichTextField/RichTextBlock is converted into segments, all translatable segments are stripped out of the
    block and stored as String instances. The remaining HTML is saved as a Template and is used for recombining the
    translated strings back into a rich text value.

    Attributes:
        template (TextField): The template value
        uuid (UUIDField): A hash of the template contents for efficient indexing.
        template_format (CharField): The format of the template (currently, only 'html' is supported).
        string_count (PositiveIntegerField): The number of translatable stirngs that were extracted from the template.
    """

    BASE_UUID_NAMESPACE = uuid.UUID("4599eabc-3f8e-41a9-be61-95417d26a8cd")

    uuid = models.UUIDField(unique=True)
    template = models.TextField()
    template_format = models.CharField(max_length=100)
    string_count = models.PositiveIntegerField()

    @classmethod
    def from_value(cls, template_value):
        """
        Gets or creates a Template instance from a TemplateValue object.

        Args:
            template_value (TemplateValue): The value of the template.

        Returns:
            Template: The Template instance that corresponds with the given template_value.
        """
        uuid_namespace = uuid.uuid5(cls.BASE_UUID_NAMESPACE, template_value.format)

        template, created = cls.objects.get_or_create(
            uuid=uuid.uuid5(uuid_namespace, template_value.template),
            defaults={
                "template": template_value.template,
                "template_format": template_value.format,
                "string_count": template_value.string_count,
            },
        )

        return template


class SegmentOverride(models.Model):
    """
    Stores the overridden value of an OverridableSegment.

    Some segments are not translatable, but can be optionally overridden in translations. For example, images.

    If an overridable segment is overridden by a user for a locale, the value to override the segment with is stored
    in this model.

    Attributes:
        locale (ForeignKey to Locale): The Locale to override.
        context (ForeignKey to TranslationContext): The context to override. With the Locale, this tells us specifically
            which object/content path to override.
        last_translated_by (User): The user who last updated this override.
        created_at (DateTimeField): The date/time when the override was first created.
        updated_at (DateTimeField): The date/time when the override was last updated.
        data_json (TextField with JSON contents): The value to override the field with.
        has_error (BooleanField): Set to True if the value of this overtride has an error. We store overrides with
            errors in case they were edited from an external system. This allows us to display the error in Wagtail.
        field_error (TextField): if there was a database-level validation error while saving the translated object, that
            error is tored here.
    """

    locale = models.ForeignKey(
        "wagtailcore.Locale", on_delete=models.CASCADE, related_name="overrides"
    )
    # FIXME: This should be a required field
    context = models.ForeignKey(
        TranslationContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overrides",
    )
    last_translated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    data_json = models.TextField()
    has_error = models.BooleanField(default=False)

    field_error = models.TextField(blank=True)

    @property
    def data(self):
        return json.loads(self.data_json)

    def set_field_error(self, error):
        """
        Returns a string containing any validation errors on the saved value.

        Returns:
            str: The validation error if there is one.
            None: If there isn't an error.
        """
        self.has_error = True
        # TODO (someday): We currently only support one error at a time
        self.field_error = error[0].messages[0]
        self.save(update_fields=["has_error", "field_error"])

    def get_error(self):
        """
        Returns a string containing any validation errors on the saved value.

        Returns:
            str: The validation error if there is one.
            None: If there isn't an error.
        """
        # Check if a database error was raised when we last attempted to publish
        if self.has_error and self.context is not None and self.field_error:
            return self.field_error


class BaseSegment(models.Model):
    source = models.ForeignKey(TranslationSource, on_delete=models.CASCADE)
    context = models.ForeignKey(
        TranslationContext,
        on_delete=models.PROTECT,
    )
    order = models.PositiveIntegerField()

    class Meta:
        abstract = True


class StringSegmentQuerySet(models.QuerySet):
    def annotate_translation(self, locale, include_errors=False):
        """
        Adds a 'translation' field to the segments containing the
        text content of the segment translated into the specified
        locale.

        By default, this would exclude any translations that have
        an error. To include these, set `include_errors` to True.
        """
        translations = StringTranslation.objects.filter(
            translation_of_id=OuterRef("string_id"),
            locale_id=pk(locale),
            context_id=OuterRef("context_id"),
        )

        if not include_errors:
            translations = translations.exclude(has_error=True)

        return self.annotate(translation=Subquery(translations.values("data")))

    def get_translations(self, locale):
        """
        Returns a queryset of StringTranslations that match any of the
        strings in this queryset.
        """
        return StringTranslation.objects.filter(
            id__in=self.annotate(
                translation_id=Subquery(
                    StringTranslation.objects.filter(
                        translation_of_id=OuterRef("string_id"),
                        locale_id=pk(locale),
                        context_id=OuterRef("context_id"),
                    ).values("id")
                )
            ).values_list("translation_id", flat=True)
        )


class StringSegment(BaseSegment):
    """
    Represents a translatable string that was extracted from a TranslationSource.

    Attributes:
        string (ForeignKey to String): The string that was extracted.
        attrs (TextField with JSON contents): The HTML attributes that were extracted from the string.

            When we extract the segment, we replace HTML attributes with ``id`` attributes and the attributes that were
            removed are stored in this field. When the translated strings come back, we replace the ``id`` attributes
            with the original HTML attributes.

            For example, for this segment:

            ``<a href="https://www.example.com">Link to example.com</a>``

            We will remove the ``href`` tag from it and replace it with an ``id``:

            ``<a id="a1">Link to example.com</a>``

            And then this field will be populated with the following JSON:

            ``` json
            {
                "a#a1": {
                    "href": "https://www.example.com"
                }
            }
            ```

        source (ForiegnKey[TranslationSource]): The source content that the string was extracted from.
        context (ForeignKey to TranslationContext): The context, which contains the position of the string in the source content.
        order (PositiveIntegerField): The index that this segment appears on the page.
    """

    string = models.ForeignKey(
        String, on_delete=models.CASCADE, related_name="segments"
    )
    attrs = models.TextField(blank=True)

    objects = StringSegmentQuerySet.as_manager()

    @classmethod
    def from_value(cls, source, language, value):
        """
        Gets or creates a TemplateSegment instance from a TemplateValue object.

        Args:
            source (TranslationSource): The source the template value was extracted from.
            template_value (TemplateValue): The value of the template.

        Returns:
            TemplateSegment: The TemplateSegment instance that corresponds with the given template_value and source.
        """
        string = String.from_value(language, value.string)
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id,
            path=value.path,
        )

        segment, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=value.order,
            string=string,
            attrs=json.dumps(value.attrs, cls=DjangoJSONEncoder),
        )

        return segment


class TemplateSegment(BaseSegment):
    """
    Represents a template segment that was extracted from a TranslationSource.

    Attributes:
        template (ForeignKey to Template): The template that was extracted.
        source (ForeignKey[TranslationSource]): The source content that the string was extracted from.
        context (ForeignKey to TranslationContext): The context, which contains the position of the string in the source content.
        order (PositiveIntegerField): The index that this segment appears on the page.
    """

    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="segments"
    )

    @classmethod
    def from_value(cls, source, value):
        """
        Gets or creates a TemplateSegment instance from a TemplateValue object.

        Args:
            source (TranslationSource): The source the template value was extracted from.
            template_value (TemplateValue): The value of the template.

        Returns:
            TemplateSegment: The TemplateSegment instance that corresponds with the given template_value and source.
        """
        template = Template.from_value(value)
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id,
            path=value.path,
        )

        segment, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=value.order,
            template=template,
        )

        return segment


class RelatedObjectSegment(BaseSegment):
    """
    Represents a related object segment that was extracted from a TranslationSource.

    Attributes:
        object (ForeignKey to TranslatableObject): The TranslatableObject instance that represents the related object.
        source (ForeignKey to TranslationSource): The source content that the string was extracted from.
        context (ForeignKey to TranslationContext): The context, which contains the position of the string in the source content.
        order (PositiveIntegerField): The index that this segment appears on the page.
    """

    object = models.ForeignKey(
        TranslatableObject, on_delete=models.CASCADE, related_name="references"
    )

    def get_source_instance(self):
        return self.object.get_instance_or_none(self.source.locale)

    @classmethod
    def from_value(cls, source, value):
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id,
            path=value.path,
        )

        segment, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=value.order,
            object=TranslatableObject.objects.get_or_create(
                content_type=value.content_type,
                translation_key=value.translation_key,
            )[0],
        )

        return segment


class OverridableSegmentQuerySet(models.QuerySet):
    def annotate_override_json(self, locale, include_errors=False):
        """
        Adds an 'override_json' field to the segments containing the
        JSON-formatted data for segments that have been overriden.

        By default, this would exclude any overrides that have
        an error. To include these, set `include_errors` to True.
        """
        overrides = SegmentOverride.objects.filter(
            locale_id=pk(locale),
            context_id=OuterRef("context_id"),
        )

        if not include_errors:
            overrides = overrides.exclude(has_error=True)

        return self.annotate(override_json=Subquery(overrides.values("data_json")))

    def get_overrides(self, locale):
        """
        Returns a queryset of SegmentOverrides that override any of the
        segments in this queryset.
        """
        return SegmentOverride.objects.filter(
            id__in=self.annotate(
                override_id=Subquery(
                    SegmentOverride.objects.filter(
                        locale_id=pk(locale),
                        context_id=OuterRef("context_id"),
                    ).values("id")
                )
            ).values_list("override_id", flat=True)
        )


class OverridableSegment(BaseSegment):
    """
    Represents an overridable segment that was extracted from a TranslationSource.

    Attributes:
        data_json (TextField with JSON content): The value of the overridable segment as it is in the source.
        source (ForeignKey to TranslationSource): The source content that the string was extracted from.
        context (ForeignKey to TranslationContext): The context, which contains the position of the string in the source content.
        order (PositiveIntegerField): The index that this segment appears on the page.
    """

    data_json = models.TextField()

    objects = OverridableSegmentQuerySet.as_manager()

    @property
    def data(self):
        """
        Returns the decoded JSON data that's stored in .data_json
        """
        return json.loads(self.data_json)

    @classmethod
    def from_value(cls, source, value):
        context, context_created = TranslationContext.objects.get_or_create(
            object_id=source.object_id,
            path=value.path,
        )

        segment, created = cls.objects.get_or_create(
            source=source,
            context=context,
            order=value.order,
            data_json=json.dumps(value.data, cls=DjangoJSONEncoder),
        )

        return segment


def disable_translation_on_delete(instance, **kwargs):
    """
    When either a source or destination object is deleted, disable the translation record.
    """
    Translation.objects.filter(
        source__object_id=instance.translation_key, enabled=True
    ).filter(
        # Disable translations where this object was the source
        Q(source__locale_id=instance.locale_id)
        # Disable translations where this object was the destination
        | Q(target_locale_id=instance.locale_id)
    ).update(
        enabled=False
    )


def cleanup_translation_on_delete(instance, **kwargs):
    """
    When either the source or destination object is deleted, remove the corresponding translation data.

    When all translations of the object are removed, delete all remaining metadata.
    """
    translation_key = instance.translation_key
    locale_id = instance.locale_id

    StringTranslation.objects.filter(
        context__object_id=translation_key, locale=locale_id
    ).delete()
    SegmentOverride.objects.filter(
        context__object__translation_key=translation_key, locale=locale_id
    ).delete()
    Translation.objects.filter(source__object_id=translation_key).filter(
        # Remove the translations where this object was the source
        Q(source__locale_id=locale_id)
        # Remove the translations where this object was the destination
        | Q(target_locale_id=locale_id)
    ).delete()

    # There are no more translations for this key, so do the full cleanup.
    if not Translation.objects.filter(source__object_id=translation_key).exists():
        # Must be done separately because of `on_delete=models.Protect`
        for model in [
            OverridableSegment,
            RelatedObjectSegment,
            StringSegment,
            TemplateSegment,
        ]:
            model.objects.filter(context__object_id=translation_key).delete()

        for model in [SegmentOverride, StringTranslation]:
            model.objects.filter(
                context__object__translation_key=translation_key
            ).delete()

        # This will cascade to TranslationSource, TranslationLog, TranslationContext as well as any extracted segments.
        TranslatableObject.objects.filter(translation_key=translation_key).delete()


def handle_translation_on_delete(instance, **kwargs):
    if getattr(settings, "WAGTAILLOCALIZE_DISABLE_ON_DELETE", False):
        disable_translation_on_delete(instance, **kwargs)
    else:
        cleanup_translation_on_delete(instance, **kwargs)


def register_post_delete_signal_handlers():
    for model in get_translatable_models():
        post_delete.connect(handle_translation_on_delete, sender=model)


class LocaleSynchronizationModelForm(LocaleComponentModelForm):
    def validate_with_locale(self, locale):
        # Note: we must compare the language_codes as it may be the same locale record,
        # but the language_code was updated in this request
        if (
            "sync_from" in self.cleaned_data
            and locale.language_code == self.cleaned_data["sync_from"].language_code
        ):
            raise ValidationError(
                {"sync_from": _("This locale cannot be synced into itself.")}
            )


@register_locale_component(
    heading=gettext_lazy("Synchronise content from another locale"),
    help_text=gettext_lazy(
        "Choose a locale to synchronise content from. "
        "Any existing and future content authored in the selected locale will "
        "be automatically copied to this one."
    ),
)
class LocaleSynchronization(models.Model):
    """
    Stores the "Sync from" setting that users can add to Locales.

    This tells Wagtail Localize to synchronise the contents of the 'sync_from' Locale to the 'locale' Locale.

    Attributes:
        locale (ForeignKey to Locale): The destination Locale of the synchronisation
        sync_from (ForeignKey to Locale): The source Locale of the synchronisation
    """

    locale = models.OneToOneField(
        "wagtailcore.Locale", on_delete=models.CASCADE, related_name="+"
    )
    sync_from = models.ForeignKey(
        "wagtailcore.Locale", on_delete=models.CASCADE, related_name="+"
    )

    base_form_class = LocaleSynchronizationModelForm

    def sync_trees(self, *, page_index=None):
        from .synctree import synchronize_tree

        background.enqueue(
            synchronize_tree,
            args=[self.sync_from, self.locale],
            kwargs={"page_index": page_index},
        )


@receiver(post_save, sender=LocaleSynchronization)
def sync_trees_on_locale_sync_save(instance, **kwargs):
    instance.sync_trees()
