import os
import uuid

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils import translation
from wagtail.core.models import Page
from wagtail.core.signals import page_published
from wagtail.images.models import AbstractImage

from .compat import get_languages, get_supported_language_variant
from .edit_handlers import filter_edit_handler_on_instance_bound
from .fields import TranslatableField, SynchronizedField
from .utils import find_available_slug


class LanguageManager(models.Manager):
    use_in_migrations = True

    def default(self):
        default_code = get_supported_language_variant(settings.LANGUAGE_CODE)
        return self.get(code=default_code)

    def default_id(self):
        return self.default().id


class Language(models.Model):
    code = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    objects = LanguageManager()

    class Meta:
        ordering = ["-is_active", "code"]

    @classmethod
    def get_active(cls):
        default_code = get_supported_language_variant(translation.get_language())

        language, created = cls.objects.get_or_create(code=default_code)

        return language

    def as_rfc5646_language_tag(self):
        """
        Returns the language code using the capitalisation as specified in RFC5646.

        For example: en-GB (not en-gb or en_GB)

        https://tools.ietf.org/html/rfc5646
        """
        # These are all the script codes that are used in Django's default LANGUAGES
        # They need to be capitalised differently from countries
        script_codes = ["latn", "hans", "hant"]

        components = self.code.split("-")

        if len(components) == 1:
            # en
            return self.code.lower()
        elif len(components) == 2:
            # en-gb or zh-hans

            if components[1] in script_codes:
                # zh-hans => zh-Hans
                return components[0].lower() + "-" + components[1].title()
            else:
                # en-gb => en-GB
                return components[0].lower() + "-" + components[1].upper()
        else:
            # Too many components. Not sure what to do.
            return self.code

    @classmethod
    def get_by_rfc5646_language_tag(cls, language_tag):
        return cls.objects.get(code=language_tag.lower())

    def get_display_name(self):
        return get_languages().get(self.code)

    def __str__(self):
        display_name = self.get_display_name()

        if display_name:
            return "{} ({})".format(display_name, self.code)
        else:
            return self.code


class RegionManager(models.Manager):
    use_in_migrations = True

    def default(self):
        return self.filter(is_default=True).first()

    def default_id(self):
        default = self.default()

        if default:
            return default.id


class Region(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    languages = models.ManyToManyField(Language)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = RegionManager()

    class Meta:
        ordering = ["-is_active", "-is_default", "name"]

    def __str__(self):
        return self.name


# Add new languages to default region automatically
# This allows sites that don't care about regions to still work
@receiver(post_save, sender=Language)
def add_new_languages_to_default_region(sender, instance, created, **kwargs):
    if created:
        default_region = Region.objects.default()

        if default_region is not None:
            default_region.languages.add(instance)


class LocaleManager(models.Manager):
    use_in_migrations = True

    def default(self):
        locale, created = self.get_or_create(
            region_id=Region.objects.default_id(),
            language_id=Language.objects.default_id(),
            is_active=True,
        )

        return locale

    def default_id(self):
        return self.default().id


# A locale gives an individual record to a region/language combination
# I prefer this way as it allows you to easily reorganise your regions and languages
# after there is already content entered.
# Note: these are managed entirely through signal handlers so don't update them directly
# without also updating the Language/Region models as well.
class Locale(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="locales")
    language = models.ForeignKey(
        Language, on_delete=models.CASCADE, related_name="locales"
    )
    is_active = models.BooleanField(default=True)

    objects = LocaleManager()

    class Meta:
        unique_together = [("region", "language")]
        ordering = [
            "-is_active",
            "-region__is_default",
            "region__name",
            "language__code",
        ]

    # For backwards compatibility
    @classmethod
    def default(cls):
        return cls.objects.default()

    # For backwards compatibility
    @classmethod
    def default_id(cls):
        return cls.objects.default_id()

    def __str__(self):
        return "{} / {}".format(self.region.name, self.language.get_display_name())

    @property
    def slug(self):
        slug = self.language.code

        if self.region != Region.objects.default():
            return "{}-{}".format(self.region.slug, self.language.code)
        else:
            return self.language.code

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


# Update Locale.is_active when Language.is_active is changed
@receiver(post_save, sender=Language)
def update_locales_on_language_change(sender, instance, **kwargs):
    if instance.is_active:
        # Activate locales iff the language is selected on the region
        (
            Locale.objects.annotate(
                is_active_on_region=Exists(
                    Region.languages.through.objects.filter(
                        region_id=OuterRef("region_id"), language_id=instance.id
                    )
                )
            )
            .filter(
                language=instance,
                region__is_active=True,
                is_active_on_region=True,
                is_active=False,
            )
            .update(is_active=True)
        )

    else:
        # Deactivate locales with this language
        Locale.objects.filter(language=instance, is_active=True).update(is_active=False)


# Update Locale.is_active when Region.is_active is changed
@receiver(post_save, sender=Region)
def update_locales_on_region_change(sender, instance, **kwargs):
    if instance.is_active:
        # Activate locales with this region
        (
            Locale.objects.annotate(
                is_active_on_region=Exists(
                    Region.languages.through.objects.filter(
                        region_id=instance.id, language_id=OuterRef("language_id")
                    )
                )
            )
            .filter(region=instance, is_active_on_region=True, is_active=False)
            .update(is_active=True)
        )

    else:
        # Deactivate locales with this region
        Locale.objects.filter(region=instance, is_active=True).update(is_active=False)


# Add/remove locales when languages are added/removed from regions
@receiver(m2m_changed, sender=Region.languages.through)
def update_locales_on_region_languages_change(
    sender, instance, action, pk_set, **kwargs
):
    if action == "post_add":
        for language_id in pk_set:
            Locale.objects.update_or_create(
                region=instance,
                language_id=language_id,
                defaults={
                    # Note: only activate locale if language is active
                    "is_active": Language.objects.filter(
                        id=language_id, is_active=True
                    ).exists()
                },
            )
    elif action == "post_remove":
        for language_id in pk_set:
            Locale.objects.update_or_create(
                region=instance, language_id=language_id, defaults={"is_active": False}
            )


def default_locale_id():
    return Locale.objects.default_id()


class TranslatableMixin(models.Model):
    translation_key = models.UUIDField(default=uuid.uuid4, editable=False)
    locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, related_name="+", default=default_locale_id
    )
    is_source_translation = models.BooleanField(default=True)

    translatable_fields = []

    def get_translations(self, inclusive=False):
        translations = self.__class__.objects.filter(
            translation_key=self.translation_key
        )

        if inclusive is False:
            translations = translations.exclude(id=self.id)

        return translations

    def get_translation(self, locale):
        return self.get_translations(inclusive=True).get(locale=locale)

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
        return self.get_translations(inclusive=True).filter(locale=locale).exists()

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

    @classmethod
    def get_synchronized_fields(cls):
        return [
            field
            for field in cls.translatable_fields
            if isinstance(field, SynchronizedField)
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

            original_process_child_object = kwargs.pop("process_child_object")

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

        # If this page is a translation, retrieve the values of all synchronised fields from the live version
        if not self.is_source_translation:
            for field in self.get_synchronized_fields():
                setattr(page, field.field_name, getattr(self, field.field_name))

        return page

    @classmethod
    def get_edit_handler(cls):
        # Translatable and Synchronised fields should not be editable
        # on translations
        translatable_fields_by_name = {
            field.field_name: field for field in cls.translatable_fields
        }

        def filter_editable_fields(edit_handler, instance):
            if not hasattr(edit_handler, "field_name"):
                return True

            if not edit_handler.field_name in translatable_fields_by_name:
                return True

            return translatable_fields_by_name[edit_handler.field_name].is_editable(
                instance
            )

        return filter_edit_handler_on_instance_bound(
            super().get_edit_handler(), filter_editable_fields
        ).bind_to(model=cls)

    class Meta:
        abstract = True
        unique_together = [("translation_key", "locale")]


class TranslatablePageRoutingMixin:
    def get_translation_for_request(self, request):
        """
        Returns the translation of this page that should be used to route
        the specified request.
        """
        language_code = translation.get_supported_language_variant(
            request.LANGUAGE_CODE
        )

        try:
            locale = Locale.objects.get(
                language__code=language_code, region__is_default=True
            )
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


@receiver(page_published)
def update_synchronised_pages_on_publish(sender, instance, revision, **kwargs):
    # This is called whenever a page is published.
    # If the page class is translatable, the page itself is a translation source, and
    # it has synchronised fields, here is where we update the synchronised fields on
    # the translated pages.

    # We only need to update the database version of the translated pages. When a revision
    # of a translated page is retrieved as a page object, the synchronised fields will be
    # copied from the database version (see TranslatablePageMixin.with_content_json)
    if not isinstance(instance, TranslatablePageMixin):
        return

    update_fields = {}

    for field in instance.translatable_fields:
        if field.is_synchronized(instance):
            update_fields[field.field_name] = field.get_value(instance)

    if update_fields:
        instance.get_translations(inclusive=False).update(**update_fields)
