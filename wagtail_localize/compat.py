import functools
from collections import defaultdict

from django.conf import settings
from django.conf.locale import LANG_INFO
from django.core.signals import setting_changed
from django.db import models, transaction
from django.dispatch import receiver
from django.utils.translation import check_for_language
from modelcluster.models import get_all_child_m2m_relations, get_all_child_relations


@functools.lru_cache()
def get_languages():
    """
    Cache of settings.LANGUAGES in a dictionary for easy lookups by key.
    """
    return dict(settings.LANGUAGES)


# Added in Django 2.1
@functools.lru_cache(maxsize=1000)
def get_supported_language_variant(lang_code, strict=False):
    """
    Return the language code that's listed in supported languages, possibly
    selecting a more generic variant. Raise LookupError if nothing is found.
    If `strict` is False (the default), look for a country-specific variant
    when neither the language code nor its generic variant is found.
    lru_cache should have a maxsize to prevent from memory exhaustion attacks,
    as the provided language codes are taken from the HTTP request. See also
    <https://www.djangoproject.com/weblog/2007/oct/26/security-fix/>.
    """
    if lang_code:
        # If 'fr-ca' is not supported, try special fallback or language-only 'fr'.
        possible_lang_codes = [lang_code]
        try:
            possible_lang_codes.extend(LANG_INFO[lang_code]["fallback"])
        except KeyError:
            pass
        generic_lang_code = lang_code.split("-")[0]
        possible_lang_codes.append(generic_lang_code)
        supported_lang_codes = get_languages()

        for code in possible_lang_codes:
            if code in supported_lang_codes and check_for_language(code):
                return code
        if not strict:
            # if fr-fr is not supported, try fr-ca.
            for supported_code in supported_lang_codes:
                if supported_code.startswith(generic_lang_code + "-"):
                    return supported_code
    raise LookupError(lang_code)


@receiver(setting_changed)
def reset_cache(**kwargs):
    """
    Clear cache when global LANGUAGES/LANGUAGE_CODE settings are changed
    """
    if kwargs["setting"] in ("LANGUAGES", "LANGUAGE_CODE"):
        get_languages.cache_clear()
        get_supported_language_variant.cache_clear()


# Next to methods implemented in https://github.com/wagtail/wagtail/pull/5762


def sync_fields_with(page, other, exclude_fields=None):
    default_exclude_fields = [
        "id",
        "content_type",
        "path",
        "depth",
        "numchild",
        "url_path",
        "draft_title",
        "live",
        "has_unpublished_changes",
        "owner",
        "locked",
        "locked_by",
        "locked_at",
        "live_revision",
        "first_published_at",
        "last_published_at",
        "latest_revision_created_at",
        "index_entries",
    ]
    exclude_fields = (
        default_exclude_fields + page.exclude_fields_in_copy + (exclude_fields or [])
    )

    if page.__class__ != other.__class__:
        raise TypeError("Page types do not match.")

    for field in page._meta.get_fields():
        # Ignore explicitly excluded fields
        if field.name in exclude_fields:
            continue

        # Ignore reverse relations
        if field.auto_created:
            continue

        # Ignore m2m relations - they will be copied as child objects
        # if modelcluster supports them at all (as it does for tags)
        if field.many_to_many:
            continue

        # Ignore parent links (page_ptr)
        if isinstance(field, models.OneToOneField) and field.remote_field.parent_link:
            continue

        setattr(page, field.name, getattr(other, field.name))

        # Special case: If the title was just synced, update draft title as well
        if field.name == "title":
            page.draft_title = page.title


def sync_child_relations_with(
    page, other, exclude_fields=None, process_child_object=None
):
    exclude_fields = exclude_fields or []

    if page.__class__ != other.__class__:
        raise TypeError("Page types do not match.")

    # copy child m2m relations
    for related_field in get_all_child_m2m_relations(page):
        field = getattr(other, related_field.name)
        if field and hasattr(field, "all"):
            values = field.all()
            if values:
                setattr(page, related_field.name, values)

    # A dict that maps child objects to their new ids
    # Used to remap child object ids in revisions
    child_object_id_map = defaultdict(dict)

    # Copy child objects
    for child_relation in get_all_child_relations(page):
        accessor_name = child_relation.get_accessor_name()

        if accessor_name in exclude_fields:
            continue

        parental_key_name = child_relation.field.attname
        child_objects = getattr(other, accessor_name, None)

        # Check for any existing child objects
        # If there are any, recycle their IDs
        with transaction.atomic():
            child_object_ids = list(
                getattr(page, accessor_name).values_list("pk", flat=True)
            )

            # As we don't store a mapping of IDs between two pages, we might reimport them in
            # a different order than before.
            # This gives us the same end result, but could lead to unique key errors while the
            # sync is taking place. So we need to delete the existing objects first.
            getattr(page, accessor_name).all().delete()

            if child_objects:
                for child_object in child_objects.all():
                    old_pk = child_object.pk

                    try:
                        # Reuse an ID that was used before if available
                        child_object.pk = child_object_ids.pop(-1)
                    except IndexError:
                        # More child objects than there were previously, set pk to None
                        # and let the database allocate a new one
                        child_object.pk = None

                    setattr(child_object, parental_key_name, page.id)

                    if process_child_object is not None:
                        process_child_object(other, page, child_relation, child_object)

                    child_object.save()

                    # Add mapping to new primary key (so we can apply this change to revisions)
                    child_object_id_map[accessor_name][old_pk] = child_object.pk

    return child_object_id_map
