import os
import uuid

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils import translation
from wagtail.core.models import Page
from wagtail.images.models import AbstractImage

from .compat import get_supported_language_variant
from .utils import find_available_slug


class Language(models.Model):
    code = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def default(cls):
        default_code = get_supported_language_variant(settings.LANGUAGE_CODE)

        language, created = cls.objects.get_or_create(
            code=default_code,
        )

        return language

    @classmethod
    def default_id(cls):
        return cls.default().id

    @classmethod
    def get_active(cls):
        default_code = get_supported_language_variant(translation.get_language())

        language, created = cls.objects.get_or_create(
            code=default_code,
        )

        return language

    def __str__(self):
        language_name = dict(settings.LANGUAGES).get(self.code)

        if language_name:
            return f'{language_name} ({self.code})'
        else:
            return self.code


class Region(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    languages = models.ManyToManyField(Language)

    @classmethod
    def default(cls):
        region, created = cls.objects.get_or_create(
            slug='default',
            defaults={
                'name': 'Default',
            }
        )

        if created:
            region.languages.add(Language.default())

        return region

    @classmethod
    def default_id(cls):
        return cls.default().id

    def __str__(self):
        return self.name


# Add new languages to default region automatically
# This allows sites that don't care about regions to still work
@receiver(post_save, sender=Language)
def add_new_languages_to_default_region(sender, instance, created, **kwargs):
    if created:
        default_region = Region.default()

        if default_region is not None:
            default_region.languages.add(instance)


# A locale gives an individual record to a region/language combination
# I prefer this way as it allows you to easily reorganise your regions and languages
# after there is already content entered.
# Note: these are managed entirely through signal handlers so don't update them directly
# without also updating the Language/Region models as well.
class Locale(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='locales')
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='locales')
    is_active = models.BooleanField()

    @classmethod
    def default(cls):
        locale, created = cls.objects.get_or_create(
            region=Region.default(),
            language=Language.default(),
            is_active=True,
        )

        return locale

    @classmethod
    def default_id(cls):
        return cls.default().id

    class Meta:
        unique_together = [
            ('region', 'language'),
        ]


# Update Locale.is_active when Language.is_active is changed
@receiver(post_save, sender=Language)
def update_locales_on_language_change(sender, instance, **kwargs):
    if instance.is_active:
        # Activate locales iff the language is selected on the region
        (
            Locale.objects
            .annotate(
                is_active_on_region=Exists(
                    Region.languages.through.objects.filter(
                        region_id=OuterRef('region_id'),
                        language_id=instance.id,
                    )
                )
            )
            .filter(
                language=instance,
                is_active_on_region=True,
                is_active=False,
            )
            .update(is_active=True)
        )

    else:
        # Deactivate locales with this language
        Locale.objects.filter(language=instance, is_active=True).update(is_active=False)


# Add/remove locales when languages are added/removed from regions
@receiver(m2m_changed, sender=Region.languages.through)
def update_locales_on_region_change(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        for language_id in pk_set:
            Locale.objects.update_or_create(
                region=instance,
                language_id=language_id,
                defaults={
                    # Note: only activate locale if language is active
                    'is_active': Language.objects.filter(id=language_id, is_active=True).exists(),
                }
            )
    elif action == 'post_remove':
        for language_id in pk_set:
            Locale.objects.update_or_create(
                region=instance,
                language_id=language_id,
                defaults={
                    'is_active': False,
                }
            )


class TranslatableMixin(models.Model):
    translation_key = models.UUIDField(default=uuid.uuid4, editable=False)
    locale = models.ForeignKey(Locale, on_delete=models.PROTECT, related_name='+', default=Locale.default_id)

    def get_translations(self, inclusive=False, all_regions=False):
        translations = self.__class__.objects.filter(translation_key=self.translation_key)

        if inclusive is False:
            translations = translations.exclude(id=self.id)

        if all_regions is False:
            translations = translations.filter(region=self.region)

        return translations

    def get_translation(self, language):
        if isinstance(language, str):
            return self.get_translations(inclusive=True).get(language__code=language)
        else:
            return self.get_translations(inclusive=True).get(language=language)

    def has_translation(self, language):
        if isinstance(language, str):
            return self.get_translations(inclusive=True).filter(language__code=language).exists()
        else:
            return self.get_translations(inclusive=True).filter(language=language).exists()

    def copy_for_translation(self, language):
        """
        Copies this instance for the specified language.
        """
        translated = self.__class__.objects.get(id=self.id)
        translated.id = None
        translated.language = language

        if isinstance(self, AbstractImage):
            # As we've copied the image record we also need to copy the original image file itself.
            # This is in case either image record is changed or deleted, the other record will still
            # have its file.
            file_stem, file_ext = os.path.splitext(self.file.name)
            new_name = f'{file_stem}-{language}{file_ext}'
            translated.file = ContentFile(self.file.read(), name=new_name)

        return translated

    @classmethod
    def get_translation_model(self):
        """
        Gets the model which manages the translations for this model.
        (The model that has the "translation_key" and "language" fields)
        Most of the time this would be the current model, but some sites
        may have intermediate concrete models between wagtailcore.Page and
        the specfic page model.
        """
        return self._meta.get_field('language').model

    class Meta:
        abstract = True
        unique_together = [
            ('translation_key', 'locale'),
        ]


class TranslatablePageMixin(TranslatableMixin):

    def copy(self, reset_translation_key=True, **kwargs):
        # If this is a regular copy (not copy_for_translation) we should change the translation_key
        # of the page and all child objects so they don't clash with the original page

        if reset_translation_key:
            if 'update_attrs' in kwargs:
                if 'translation_key' not in kwargs['update_attrs']:
                    kwargs['update_attrs']['translation_key'] = uuid.uuid4()

            else:
                kwargs['update_attrs'] = {
                    'translation_key': uuid.uuid4(),
                }

            original_process_child_object = kwargs.pop('process_child_object')

            def process_child_object(child_relation, child_object):
                # Change translation keys of translatable child objects
                if isinstance(child_object, TranslatableMixin):
                    child_object.translation_key = uuid.uuid4()

                if original_process_child_object is not None:
                    original_process_child_object(child_relation, child_object)

            kwargs['process_child_object'] = process_child_object

        return super().copy(**kwargs)

    def copy_for_translation(self, language, copy_parents=False):
        """
        Copies this page for the specified language.
        """
        # Find the translated version of the parent page to create the new page under
        parent = self.get_parent().specific
        slug = self.slug
        if isinstance(parent, TranslatableMixin):
            try:
                translated_parent = parent.get_translation(language)
            except parent.__class__.DoesNotExist:
                if not copy_parents:
                    return

                translated_parent = parent.copy_for_translation(language, copy_parents=True)
        else:
            translated_parent = parent

            # Append language code to slug as the new page
            # will be created in the same section as the existing one
            slug += '-' + language.code

        # Find available slug for new page
        slug = find_available_slug(translated_parent, slug)

        # Update language on translatable child objects as well
        def process_child_object(child_relation, child_object):
            if isinstance(child_object, TranslatableMixin):
                child_object.language = language

        return self.copy(
            to=translated_parent,
            update_attrs={'language': language, 'slug': slug},
            copy_revisions=False,
            keep_live=False,
            reset_translation_key=False,
            process_child_object=process_child_object,
        )

    def get_translation_for_request(self, request):
        """
        Returns the translation of this page that should be used to route
        the specified request.
        """
        language_code = translation.get_supported_language_variant(request.LANGUAGE_CODE)

        try:
            language = Language.objects.get(code=language_code)
            return self.get_translation(language)

        except Language.DoesNotExist:
            return

        except Page.DoesNotExist:
            return

    def route(self, request, path_components):
        # When this mixin is applied to a page, this override
        # will change the routing behaviour to route requests to
        # the correct translation based on the language code on
        # the request.

        # Check that an ancestor hasn't already routed the request into
        # a single-language section of the site.
        if not getattr(request, '_wagtail_i18n_routed', False):
            # If the site root is translatable, reroute based on language
            page = self.get_translation_for_request(request)

            if page is not None:
                request._wagtail_i18n_routed = True
                return page.route(request, path_components)

        return super().route(request, path_components)

    class Meta:
        abstract = True
        unique_together = [
            ('translation_key', 'locale'),
        ]


class BootstrapTranslatableMixin(TranslatableMixin):
    """
    A version of TranslatableMixin without uniqueness constraints.

    This is to make it easy to transition existing models to being translatable.

    The process is as follows:
     - Add BootstrapTranslatableMixin to the model
     - Run makemigrations
     - Create a data migration for each app, then use the BootstrapTranslatableModel operation in
       wagtail_i18n.bootstrap on each model in that app
     - Change BootstrapTranslatableMixin to TranslatableMixin (or TranslatablePageMixin, if it's a page model)
     - Run makemigrations again
     - Migrate!
    """
    translation_key = models.UUIDField(null=True, editable=False)

    class Meta:
        abstract = True


def get_translatable_models(include_subclasses=False):
    """
    Returns a list of all concrete models that inherit from TranslatableMixin.
    By default, this only includes models that are direct children of TranslatableMixin,
    to get all models, set the include_subclasses attribute to True.
    """
    translatable_models = [
        model for model in apps.get_models()
        if issubclass(model, TranslatableMixin) and not model._meta.abstract
    ]

    if include_subclasses is False:
        # Exclude models that inherit from another translatable model
        root_translatable_models = set()

        for model in translatable_models:
            root_translatable_models.add(model.get_translation_model())

        translatable_models = [
            model for model in translatable_models
            if model in root_translatable_models
        ]

    return translatable_models
