from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from wagtail.core.models import Page

from wagtail_localize.models import Translation, TranslationSource


class TranslationCreator:
    """
    A class that provides a create_translations method.

    Call create_translations for each object you want to translate and this will submit
    that object and any dependencies as well.

    This class will track the objects that have already submitted so an object doesn't
    get submitted twice.
    """

    def __init__(self, user, target_locales):
        self.user = user
        self.target_locales = target_locales
        self.seen_objects = set()
        self.mappings = defaultdict(list)

    def create_translations(self, instance, include_related_objects=True):
        if isinstance(instance, Page):
            instance = instance.specific

        if instance.translation_key in self.seen_objects:
            return
        self.seen_objects.add(instance.translation_key)

        source, created = TranslationSource.get_or_create_from_instance(instance)

        # Add related objects
        # Must be before translation records or those translation records won't be able to create
        # the objects because the dependencies haven't been created
        if include_related_objects:
            for related_object_segment in source.relatedobjectsegment_set.all():
                related_instance = related_object_segment.object.get_instance(
                    instance.locale
                )

                # Limit to one level of related objects, since this could potentially pull in a lot of stuff
                self.create_translations(
                    related_instance, include_related_objects=False
                )

        # Support disabling the out of the box translation mode.
        # The value set on the model takes precendence over the global setting.
        if hasattr(instance, "localize_default_translation_mode"):
            translation_mode = instance.localize_default_translation_mode
        else:
            translation_mode = getattr(
                settings, "WAGTAIL_LOCALIZE_DEFAULT_TRANSLATION_MODE", "synced"
            )
        translation_enabled = translation_mode == "synced"

        # Set up translation records
        for target_locale in self.target_locales:
            # Create translation if it doesn't exist yet, re-enable if translation was disabled
            # Note that the form won't show this locale as an option if the translation existed
            # in this langauge, so this shouldn't overwrite any unmanaged translations.
            translation, created = Translation.objects.update_or_create(
                source=source,
                target_locale=target_locale,
                defaults={"enabled": translation_enabled},
            )

            self.mappings[source].append(translation)

            # Determine whether or not to publish the translation.
            publish = getattr(instance, "live", True)

            try:
                translation.save_target(user=self.user, publish=publish)
            except ValidationError:
                pass


@transaction.atomic
def translate_object(instance, locales, components=None, user=None):
    """
    Translates the given object into the given locales.
    """
    translator = TranslationCreator(user, locales)
    translator.create_translations(instance)

    if components is not None:
        components.save(translator, sources_and_translations=translator.mappings)


@transaction.atomic
def translate_page_subtree(page_id, locales, components, user):
    """
    Translates the given page's subtree into the given locales.

    Note that the page itself must already be translated.

    Note: Page must be passed by ID since this function may be called with an async worker and pages can't be reliably pickled.
          See: https://github.com/wagtail/wagtail/pull/5998
    """
    page = Page.objects.get(id=page_id)

    translator = TranslationCreator(user, locales)

    def _walk(current_page):
        for child_page in current_page.get_children():
            translator.create_translations(child_page)

            if child_page.numchild:
                _walk(child_page)

    _walk(page)

    if components is not None:
        components.save(translator, sources_and_translations=translator.mappings)
