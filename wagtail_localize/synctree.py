from collections import defaultdict

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.functional import cached_property
from wagtail.core.models import Page, Locale


class PageIndex:
    """
    An in-memory index of pages to remove the need to query the database.

    Each entry in the index is a unique page by translation key, so a page
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
            "aliased_locales",
        ]

        def __init__(
            self,
            content_type,
            translation_key,
            source_locale,
            parent_translation_key,
            locales,
            aliased_locales,
        ):
            self.content_type = content_type
            self.translation_key = translation_key
            self.source_locale = source_locale
            self.parent_translation_key = parent_translation_key
            self.locales = locales
            self.aliased_locales = aliased_locales

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
            # Get parent, but only if the parent is not the root page. We consider the
            # homepage of each langauge tree to be the roots
            if page.depth > 2:
                parent_page = page.get_parent()
            else:
                parent_page = None

            return cls(
                page.content_type,
                page.translation_key,
                page.locale,
                parent_page.translation_key if parent_page else None,
                list(
                    Page.objects.filter(
                        translation_key=page.translation_key,
                        alias_of__isnull=True,
                    ).values_list("locale", flat=True)
                ),
                list(
                    Page.objects.filter(
                        translation_key=page.translation_key,
                        alias_of__isnull=False,
                    ).values_list("locale", flat=True)
                ),
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

        for page in Page.objects.filter(alias_of__isnull=True, depth__gt=1).only(
            *PageIndex.Entry.REQUIRED_PAGE_FIELDS
        ):
            pages.append(PageIndex.Entry.from_page_instance(page))

        return PageIndex(pages)


def synchronize_tree(source_locale, target_locale, *, page_index=None):
    """
    Synchronises a locale tree with the other locales.

    This creates any placeholders that don't exist yet, updates placeholders where their
    source has been changed and moves pages to match the structure of other trees
    """
    # Build a page index
    if not page_index:
        page_index = PageIndex.from_database().sort_by_tree_position()

    # Find pages that are not translated for this locale
    # This includes locales that have a placeholder, it only excludes locales that have an actual translation
    pages_not_in_locale = page_index.not_translated_into(target_locale)

    for page in pages_not_in_locale:
        # Skip pages that do not exist in the source
        if source_locale.id not in page.locales and source_locale.id not in page.aliased_locales:
            continue

        # Fetch source from database
        model = page.content_type.model_class()
        source_page = model.objects.get(
            translation_key=page.translation_key, locale=source_locale
        )

        if target_locale.id not in page.aliased_locales:
            source_page.copy_for_translation(
                target_locale, copy_parents=True, alias=True
            )


@receiver(post_save)
def on_page_saved(sender, instance, **kwargs):
    if not issubclass(sender, Page):
        return

    # We only care about creations
    if not kwargs['created']:
        return

    # Check if the source tree needs to be synchronised into any other trees
    from .models import LocaleSynchronization
    locales_to_sync_to = Locale.objects.filter(
        id__in=(
            LocaleSynchronization.objects
            .filter(sync_from_id=instance.locale_id)
            .values_list("locale_id", flat=True)
        )
    )

    # Create aliases in all those locales
    for locale in locales_to_sync_to:
        instance.copy_for_translation(
            locale, copy_parents=True, alias=True
        )
