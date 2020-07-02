import os
import uuid

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.dispatch import receiver
from django.utils import translation
from modelcluster.fields import ParentalKey
from wagtail.core.models import Page
from wagtail.core.signals import page_published
from wagtail.images.models import AbstractImage

from .compat import get_languages, get_supported_language_variant
from .edit_handlers import filter_edit_handler_on_instance_bound
from .fields import TranslatableField, SynchronizedField
from .utils import find_available_slug


def pk(obj):
    if isinstance(obj, models.Model):
        return obj.pk
    else:
        return obj


class LocaleManager(models.Manager):
    use_in_migrations = True

    def default(self):
        default_code = get_supported_language_variant(settings.LANGUAGE_CODE)
        return self.get(language_code=default_code)

    def default_id(self):
        return self.default().id


class Locale(models.Model):
    language_code = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    objects = LocaleManager()

    class Meta:
        ordering = [
            "-is_active",
            "language_code",
        ]

    def get_display_name(self):
        return get_languages().get(self.language_code)

    def __str__(self):
        return self.get_display_name() or self.language_code

    @classmethod
    def get_active(cls):
        active_code = get_supported_language_variant(translation.get_language())

        locale, created = cls.objects.get_or_create(language_code=active_code)

        return locale

    @property
    def slug(self):
        return self.language_code

    def get_all_pages(self):
        """
        Returns a queryset of all pages that have been translated into this locale.
        """
        q = Q()

        for model in get_translatable_models():
            if not issubclass(model, Page):
                continue

            q |= Q(
                id__in=model.objects.filter(locale=self).values_list("id", flat=True)
            )

        return Page.objects.filter(q)


def default_locale_id():
    return Locale.objects.default_id()


class TranslatableMixin(models.Model):
    translation_key = models.UUIDField(default=uuid.uuid4, editable=False)
    locale = models.ForeignKey(Locale, on_delete=models.PROTECT, related_name="+", editable=False)
    is_source_translation = models.BooleanField(default=True, editable=False)

    translatable_fields = []

    def get_translations(self, inclusive=False):
        translations = self.__class__.objects.filter(
            translation_key=self.translation_key
        )

        if inclusive is False:
            translations = translations.exclude(id=self.id)

        return translations

    def get_translation(self, locale):
        return self.get_translations(inclusive=True).get(locale_id=pk(locale))

    def get_translation_or_none(self, locale):
        try:
            return self.get_translation(locale)
        except self.__class__.DoesNotExist:
            return None

    def get_source_translation(self):
        if self.is_source_translation:
            return self

        return self.get_translations(inclusive=False).get(is_source_translation=True)

    def has_translation(self, locale):
        return self.get_translations(inclusive=True).filter(locale_id=pk(locale)).exists()

    def copy_for_translation(self, locale):
        """
        Copies this instance for the specified locale.
        """
        translated = self.__class__.objects.get(id=self.id)
        translated.id = None
        translated.locale = locale
        translated.is_source_translation = False

        if isinstance(self, AbstractImage):
            # As we've copied the image record we also need to copy the original image file itself.
            # This is in case either image record is changed or deleted, the other record will still
            # have its file.
            file_stem, file_ext = os.path.splitext(self.file.name)
            new_name = "{}-{}{}".format(file_stem, locale.slug, file_ext)
            translated.file = ContentFile(self.file.read(), name=new_name)

        return translated

    def get_default_locale_id(self):
        """
        Finds the default locale to use for this object.

        Intended to be run before save.
        """
        # Check if the object has any parental keys to another translatable model
        # If so, take the locale from the object referenced in that parental key
        parental_keys = [
            field
            for field in self._meta.get_fields()
            if isinstance(field, ParentalKey)
            and issubclass(field.related_model, TranslatableMixin)
        ]

        if parental_keys:
            parent_id = parental_keys[0].value_from_object(self)
            return (
                parental_keys[0]
                .related_model.objects.only("locale_id")
                .get(id=parent_id)
                .locale_id
            )

        return Locale.objects.default_id()

    @classmethod
    def get_translation_model(self):
        """
        Gets the model which manages the translations for this model.
        (The model that has the "translation_key" and "locale" fields)
        Most of the time this would be the current model, but some sites
        may have intermediate concrete models between wagtailcore.Page and
        the specfic page model.
        """
        return self._meta.get_field("locale").model

    @classmethod
    def get_translatable_fields(cls):
        return [
            field
            for field in cls.translatable_fields
            if isinstance(field, TranslatableField)
        ]

    class Meta:
        abstract = True
        unique_together = [("translation_key", "locale")]


class ParentNotTranslatedError(Exception):
    """
    Raised when a call to Page.copy_for_translation is made but the
    parent page is not translated and copy_parents is False.
    """

    pass


class TranslatablePageMixin(TranslatableMixin):

    class Meta:
        abstract = True
        unique_together = [("translation_key", "locale")]

    def copy(self, reset_translation_key=True, **kwargs):
        # If this is a regular copy (not copy_for_translation) we should change the translation_key
        # of the page and all child objects so they don't clash with the original page
        if reset_translation_key:
            if "update_attrs" in kwargs:
                if "translation_key" not in kwargs["update_attrs"]:
                    kwargs["update_attrs"]["translation_key"] = uuid.uuid4()
                    kwargs["update_attrs"]["is_source_translation"] = True

            else:
                kwargs["update_attrs"] = {
                    "translation_key": uuid.uuid4(),
                    "is_source_translation": True,
                }

            original_process_child_object = kwargs.pop("process_child_object", None)

            def process_child_object(
                original_page, page_copy, child_relation, child_object
            ):
                # Change translation keys of translatable child objects
                if isinstance(child_object, TranslatableMixin):
                    child_object.translation_key = uuid.uuid4()
                    child_object.is_source_translation = True

                if original_process_child_object is not None:
                    original_process_child_object(
                        original_page, page_copy, child_relation, child_object
                    )

            kwargs["process_child_object"] = process_child_object

        return super().copy(**kwargs)

    @transaction.atomic
    def copy_for_translation(self, locale, copy_parents=False, exclude_fields=None):
        """
        Copies this page for the specified locale.
        """
        # Find the translated version of the parent page to create the new page under
        parent = self.get_parent().specific
        slug = self.slug
        if isinstance(parent, TranslatablePageMixin):
            try:
                translated_parent = parent.get_translation(locale)
            except parent.__class__.DoesNotExist:
                if not copy_parents:
                    raise ParentNotTranslatedError

                translated_parent = parent.copy_for_translation(
                    locale, copy_parents=True
                )
        else:
            translated_parent = parent

            # Append locale code to slug as the new page
            # will be created in the same section as the existing one
            slug += "-" + locale.slug

        # Find available slug for new page
        slug = find_available_slug(translated_parent, slug)

        # Update locale on translatable child objects as well
        def process_child_object(
            original_page, page_copy, child_relation, child_object
        ):
            if isinstance(child_object, TranslatableMixin):
                child_object.locale = locale
                child_object.is_source_translation = False

        return self.copy(
            to=translated_parent,
            update_attrs={
                "locale": locale,
                "is_source_translation": False,
                "slug": slug,
            },
            copy_revisions=False,
            keep_live=False,
            reset_translation_key=False,
            process_child_object=process_child_object,
            exclude_fields=exclude_fields,
        )

    def get_default_locale_id(self):
        """
        Finds the default locale to use for this page.

        Intended to be run before save.
        """
        parent = self.get_parent()
        if parent is not None:
            if issubclass(parent.specific_class, TranslatablePageMixin):
                return (
                    parent.specific_class.objects.only("locale_id")
                    .get(id=parent.id)
                    .locale_id
                )

        return super().get_default_locale_id()

    def full_clean(self, **kwargs):
        # We need to override this as the locale ID needs to be set before validation
        # (normally we would set this on the pre_save signal but Wagtail does model level validation)
        if self.locale_id is None:
            self.locale_id = self.get_default_locale_id()

        return super().full_clean(**kwargs)

    def can_move_to(self, parent):
        if not super().can_move_to(parent):
            return False

        # Prevent pages being moved to different language sections
        if issubclass(parent.specific_class, TranslatablePageMixin):
            if parent.specific.locale_id != self.locale_id:
                return False

        return True

    def with_content_json(self, content_json):
        page = super().with_content_json(content_json)
        page.translation_key = self.translation_key
        page.locale = self.locale
        page.is_source_translation = self.is_source_translation

        return page

# Commented out as this prevents preview from working
#
#    @classmethod
#    def get_edit_handler(cls):
#        # Translatable and Synchronised fields should not be editable
#        # on translations
#        translatable_fields_by_name = {
#            field.field_name: field for field in cls.translatable_fields
#        }
#
#        def filter_editable_fields(edit_handler, instance):
#            if not hasattr(edit_handler, "field_name"):
#                return True
#
#            if not edit_handler.field_name in translatable_fields_by_name:
#                return True
#
#            return translatable_fields_by_name[edit_handler.field_name].is_editable(
#                instance
#            )
#
#        return filter_edit_handler_on_instance_bound(
#            super().get_edit_handler(), filter_editable_fields
#        ).bind_to(model=cls)

    def get_translation_for_request(self, request):
        """
        Returns the translation of this page that should be used to route
        the specified request.
        """
        language_code = translation.get_supported_language_variant(
            request.LANGUAGE_CODE
        )

        try:
            locale = Locale.objects.get(language_code=language_code)
            return self.get_translation(locale)

        except Locale.DoesNotExist:
            return

        except self.DoesNotExist:
            return

    def route(self, request, path_components):
        # When this mixin is applied to a page, this override
        # will change the routing behaviour to route requests to
        # the correct translation based on the language code on
        # the request.

        # Check that an ancestor hasn't already routed the request into
        # a single-language section of the site.
        if not getattr(request, "_wagtail_localize_routed", False):
            # If the site root is translatable, reroute based on language
            page = self.get_translation_for_request(request)

            if page is not None:
                request._wagtail_localize_routed = True
                return page.route(request, path_components)

        return super().route(request, path_components)


class BootstrapTranslatableMixin(TranslatableMixin):
    """
    A version of TranslatableMixin without uniqueness constraints.

    This is to make it easy to transition existing models to being translatable.

    The process is as follows:
     - Add BootstrapTranslatableMixin to the model
     - Run makemigrations
     - Create a data migration for each app, then use the BootstrapTranslatableModel operation in
       wagtail_localize.bootstrap on each model in that app
     - Change BootstrapTranslatableMixin to TranslatableMixin (or TranslatablePageMixin, if it's a page model)
     - Run makemigrations again
     - Migrate!
    """

    translation_key = models.UUIDField(null=True, editable=False)
    locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        abstract = True


def get_translatable_models(include_subclasses=False):
    """
    Returns a list of all concrete models that inherit from TranslatableMixin.
    By default, this only includes models that are direct children of TranslatableMixin,
    to get all models, set the include_subclasses attribute to True.
    """
    translatable_models = [
        model
        for model in apps.get_models()
        if issubclass(model, TranslatableMixin) and not model._meta.abstract
    ]

    if include_subclasses is False:
        # Exclude models that inherit from another translatable model
        root_translatable_models = set()

        for model in translatable_models:
            root_translatable_models.add(model.get_translation_model())

        translatable_models = [
            model for model in translatable_models if model in root_translatable_models
        ]

    return translatable_models


@receiver(pre_save)
def set_locale_on_new_instance(sender, instance, **kwargs):
    if not isinstance(instance, TranslatableMixin):
        return

    if instance.locale_id is not None:
        return

    # If this is a fixture load, use the global default Locale
    # as the page tree is probably in an flux
    if kwargs["raw"]:
        instance.locale_id = Locale.objects.default_id()
        return

    instance.locale_id = instance.get_default_locale_id()
