"""
Tree Synchronisation

This module contains all the logic for for synchronising language trees.

This provides the following functionality:

 - Creating and updating placeholder pages for content that hasn't been translated yet
 - Moving pages so that they always match their position in their source locale
"""

from collections import defaultdict

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property
from wagtail.core.models import Page
from wagtail.core.signals import page_published, page_unpublished

from .compat import sync_child_relations_with, sync_fields_with
from .models import (
    Locale,
    get_translatable_models,
    TranslatableMixin,
    TranslatablePageMixin,
)
from .utils import get_fallback_languages


class PageIndex:
    """
    An in-memory index of pages to remove the need to query the database.

    Each entry in the index is a unique page by transaction key, so a page
    that has been translated into different languages appears only once.
    """

    # Note: This has been designed to be as memory-efficient as possible, but it
    # hasn't been tested on a very large site yet.

    class Entry:
        """
        Represents a page in the index.
        """

        __slots__ = [
            "content_type",
            "translation_key",
            "source_locale",
            "parent_translation_key",
            "locales",
            "placeholder_locales",
        ]

        def __init__(
            self,
            content_type,
            translation_key,
            source_locale,
            parent_translation_key,
            locales,
            placeholder_locales,
        ):
            self.content_type = content_type
            self.translation_key = translation_key
            self.source_locale = source_locale
            self.parent_translation_key = parent_translation_key
            self.locales = locales
            self.placeholder_locales = placeholder_locales

        REQUIRED_PAGE_FIELDS = [
            "content_type",
            "translation_key",
            "locale",
            "path",
            "depth",
            "last_published_at",
            "latest_revision_created_at",
            "live",
        ]

        @classmethod
        def from_page_instance(cls, page):
            """
            Initialises an Entry from the given page instance.
            """
            # Get parent, but only if it too is translatable.
            # We don't care about untranslatable parents as we consider the first
            # translatable ancestor to be the root of any language tree.
            parent_page = page.get_parent()
            if issubclass(parent_page.specific_class, TranslatablePageMixin):
                parent_page = parent_page.specific
            else:
                parent_page = None

            return cls(
                page.content_type,
                page.translation_key,
                page.locale,
                parent_page.translation_key if parent_page else None,
                list(
                    page.__class__.objects.filter(
                        translation_key=page.translation_key,
                        placeholder_locale__isnull=True,
                    ).values_list("locale", flat=True)
                ),
                {
                    page["locale"]: {
                        "copy_of_locale": page["placeholder_locale"],
                        "last_copied_at": page["last_published_at"],
                    }
                    for page in page.__class__.objects.filter(
                        translation_key=page.translation_key,
                        placeholder_locale__isnull=False,
                    ).values("locale", "placeholder_locale", "last_published_at")
                },
            )

    def __init__(self, pages):
        self.pages = pages

    @cached_property
    def by_translation_key(self):
        return {page.translation_key: page for page in self.pages}

    @cached_property
    def by_parent_translation_key(self):
        by_parent_translation_key = defaultdict(list)
        for page in self.pages:
            by_parent_translation_key[page.parent_translation_key].append(page)

        return dict(by_parent_translation_key.items())

    def sort_by_tree_position(self):
        """
        Returns a new index with the pages sorted in depth-first-search order
        using their parent in their respective source locale.
        """
        remaining_pages = set(page.translation_key for page in self.pages)

        new_pages = []

        def _walk(translation_key):
            for page in self.by_parent_translation_key.get(translation_key, []):
                if page.translation_key not in remaining_pages:
                    continue

                remaining_pages.remove(page.translation_key)
                new_pages.append(page)
                _walk(page.translation_key)

        _walk(None)

        if remaining_pages:
            print("Warning: {} orphaned pages!".format(len(remaining_pages)))

        return PageIndex(new_pages)

    def not_translated_into(self, locale):
        """
        Returns an index of pages that are not translated into the specified locale.
        This includes pages that have and don't have a placeholder
        """
        pages = [page for page in self.pages if locale.id not in page.locales]

        return PageIndex(pages)

    def __iter__(self):
        return iter(self.pages)

    @classmethod
    def from_database(cls):
        """
        Populates the index from the database.
        """
        pages = []
        for model in get_translatable_models():
            if not issubclass(model, Page):
                continue

            for page in model.objects.filter(is_source_translation=True).only(
                *PageIndex.Entry.REQUIRED_PAGE_FIELDS
            ):
                if page.specific_class != model:
                    continue

                pages.append(PageIndex.Entry.from_page_instance(page))

        return PageIndex(pages)


@transaction.atomic
def create_placeholder(source_page, target_locale):
    translation = source_page.copy_for_translation(
        target_locale, copy_parents=True, placeholder=True, keep_live=True
    )
    translation.last_published_at = source_page.last_published_at or timezone.now()
    translation.save(update_fields=["last_published_at"])


@transaction.atomic
def update_placeholder(source_page, target_page):
    source_locale = source_page.locale
    target_locale = target_page.locale

    # Update locale on translatable child objects as well
    def process_child_object(original_page, page_copy, child_relation, child_object):
        if isinstance(child_object, TranslatableMixin):
            child_object.locale = target_locale
            child_object.is_source_translation = False

    sync_fields_with(
        target_page,
        source_page,
        exclude_fields=[
            "slug",
            "locale",
            "placeholder_locale",
            "translation_key",
            "is_source_translation",
        ],
    )
    sync_child_relations_with(
        target_page, source_page, process_child_object=process_child_object
    )
    target_page.placeholder_locale = source_locale
    target_page.locale = target_locale
    target_page.last_published_at = source_page.last_published_at or timezone.now()
    target_page.save()


def synchronize_tree(page_index, locale):
    """
    Synchronises a locale tree with the other locales.

    This creates any placeholders that don't exist yet, updates placeholders where their
    source has been changed and moves pages to match the structure of other trees
    """
    # Find pages that are not translated for this locale
    # This includes locales that have a placeholder, it only excludes locales that have an actual translation
    pages_not_in_locale = page_index.not_translated_into(locale)

    for page in pages_not_in_locale:
        source_locale = locale.get_best_fallback(page.locales)

        if source_locale is None:
            print(
                f"Cannot create placeholder of '{source_page}' in '{locale}'. No suitable source locale found"
            )
            continue

        # Fetch source from database
        model = page.content_type.model_class()
        source_page = model.objects.get(
            translation_key=page.translation_key, locale=source_locale
        )

        if locale.id not in page.placeholder_locales:
            print(f"Copying '{source_page}' into '{locale}'")
            create_placeholder(source_page, locale)

        else:
            # Update placeholder
            placeholder_info = page.placeholder_locales[locale.id]

            translation = model.objects.get(
                translation_key=page.translation_key, locale=locale
            )

            # If the fallback locale has changed, switch the placeholder to use it
            # This happens when a better version of the page comes available. For
            # example, say this page being updated was in es-MX locale, and es has
            # just been published so we can now switch to use that as a fallback
            # instead.
            if source_locale.id != placeholder_info["copy_of_locale"]:
                print(
                    f"Updating '{translation}' ({locale}) because a better fallback page is now available"
                )
                update_placeholder(source_page, translation)

            # If the fallback has been updated since last sync, update the placeholder
            # FIXME: This is not working
            elif (
                source_page.last_published_at is not None
                and placeholder_info["last_copied_at"] is not None
                and source_page.last_published_at > placeholder_info["last_copied_at"]
            ):
                print(
                    f"Updating '{translation}' ({locale}) because its fallback has changed"
                )
                update_placeholder(source_page, translation)

    # TODO: Move pages


@receiver(post_save)
def on_page_saved(sender, instance, **kwargs):
    """
    Called whenever a page is saved, whether this is a:
     - Page creation
     - Page edit
     - Creation/edit of a translation
     - Creation/edit of a placeholder (ignored)
    """
    if not getattr(settings, "WAGTAILLOCALIZE_ENABLE_PLACEHOLDERS", False):
        return

    if not isinstance(instance, TranslatablePageMixin):
        return

    # Is this a creation or an edit?
    is_creation = kwargs["created"]

    # Is this a source, translation or placeholder?
    if instance.is_source_translation:
        page_type = "source"
    elif instance.placeholder_locale is not None:
        page_type = "placeholder"
    else:
        page_type = "translation"

    # We're not interested in reacting to when placeholders are updated
    if page_type == "placeholder":
        return

    if is_creation:
        # New page is created
        # If this is the source, we need to copy for all locales
        # If this is a translation, we need to check existing placeholders and change their
        # source locale if this translation is better than the source they already have

        # Create placeholders all in locales that don't have one yet
        missing_locales = Locale.objects.exclude(
            id__in=instance.__class__.objects.filter(
                translation_key=instance.translation_key,
            ).values_list("locale_id", flat=True)
        )

        for locale in missing_locales:
            create_placeholder(instance, locale)

        # Check existing placeholders to see if this translation would be a better source for them.
        # For example, say we already have a page in en with placeholders in es/es-MX. When the page
        # is translated into es, we want to change the placeholder_locale of the es-MX to es.
        if page_type == "translation":
            # A queryset of locales that have translations
            translated_locales = Locale.objects.exclude(
                id__in=instance.__class__.objects.filter(
                    translation_key=instance.translation_key,
                    placeholder_locale__isnull=True,
                ).values_list("locale_id", flat=True)
            )

            # A queryset of locales that are currently placeholders
            placeholder_locales = Locale.objects.exclude(
                id__in=instance.__class__.objects.filter(
                    translation_key=instance.translation_key,
                    placeholder_locale__isnull=False,
                ).values_list("locale_id", flat=True)
            )

            # Find locales where this new translation provides a better fallback
            for locale in placeholder_locales:
                best_fallback_locale = locale.get_best_fallback(
                    translated_locales
                )

                if best_fallback_locale == instance.locale:
                    placeholder = instance.get_translation(locale)
                    update_placeholder(instance, placeholder)

    else:
        # A page was edited, update all placeholders that have this page as the source
        for placeholder in instance.__class__.objects.filter(
            translation_key=instance.translation_key, placeholder_locale=instance.locale
        ):
            update_placeholder(instance, placeholder)


@receiver(page_published)
def on_page_published(sender, instance, **kwargs):
    if isinstance(instance, TranslatablePageMixin):
        # Publish any placeholders that are following this page
        # We can just set live to True as placeholders don't have revisions
        instance.__class__.objects.filter(
            translation_key=instance.translation_key,
            placeholder_locale_id=instance.locale_id,
        ).update(live=True, has_unpublished_changes=False)


@receiver(page_unpublished)
def on_page_unpublished(sender, instance, **kwargs):
    if isinstance(instance, TranslatablePageMixin):
        # unpublish any placeholders that are following this page
        # We can just set live to True as placeholders don't have revisions
        instance.__class__.objects.filter(
            translation_key=instance.translation_key,
            placeholder_locale_id=instance.locale_id,
        ).update(live=False, has_unpublished_changes=True)


# @receiver(page_moved)
# def on_page_moved(sender, instance, **kwargs):
#     pass
