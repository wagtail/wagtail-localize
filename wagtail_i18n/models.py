import os
import uuid

from django.apps import apps
from django.conf import settings
from django.db import models
from django.utils import translation
from wagtail.core.models import Page
from wagtail.images.models import AbstractImage

from .utils import find_available_slug


class Language(models.Model):
    code = models.CharField(max_length=100, unique=True)

    @classmethod
    def default(cls):
        default_code = translation.get_supported_language_variant(settings.LANGUAGE_CODE)

        language, created = cls.objects.get_or_create(
            code=default_code,
        )

        return language.id


class Translatable(models.Model):
    translation_key = models.UUIDField(default=uuid.uuid4, editable=False)
    language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='+', default=Language.default)

    def get_translations(self, inclusive=False):
        translations = self.__class__.objects.filter(translation_key=self.translation_key)

        if inclusive is False:
            translations = translations.exclude(id=self.id)

        return translations

    def get_translation(self, language):
        if isinstance(language, str):
            return self.get_translations(inclusive=True).get(language__code=language)
        else:
            return self.get_translations(inclusive=True).get(language=language)

    def copy_for_translation(self, language):
        """
        Copies this instance for the specified language.
        """
        if isinstance(self, Page):
            # Use Wagtail's Page copy to copy pages

            # Find the translated version of the parent page to create the new page under
            parent = self.get_parent().specific
            slug = self.slug
            if isinstance(parent, Translatable):
                try:
                    translated_parent = parent.get_translation(language)
                except parent.__class__.DoesNotExist:
                    translated_parent = parent.copy_for_translation(language)
            else:
                translated_parent = parent

                # Append language code to slug as the new page
                # will be created in the same section as the existing one
                slug += '-' + language.code

            # Find available slug for new page
            slug = find_available_slug(translated_parent, slug)

            return self.copy(to=translated_parent, update_attrs={'language': language, 'slug': slug}, copy_revisions=False, keep_live=False)

        else:
            # For other models, fetch a new instance and remove the ID
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
            ('translation_key', 'language'),
        ]


class BootstrapTranslatable(Translatable):
    """
    A version of Translatable without uniqueness constraints.

    This is to make it easy to transition existing models to being translatable.

    The process is as follows:
     - Add BootstrapTranslatable to the model
     - Run makemigrations and migrate
     - Run bootstrap_translatable_models
     - Change BootstrapTranslatable to Translatable
     - Run makemigrations and migrate
    """
    translation_key = models.UUIDField(null=True, editable=False)

    class Meta:
        abstract = True


def get_translatable_models(include_subclasses=False):
    """
    Returns a list of all concrete models that inherit from Translatable.
    By default, this only includes models that are direct children of Translatable,
    to get all models, set the include_subclasses attribute to True.
    """
    translatable_models = [
        model for model in apps.get_models()
        if issubclass(model, Translatable) and not model._meta.abstract
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
