import functools

from django.conf import settings
from django.conf.locale import LANG_INFO
from django.core.signals import setting_changed
from django.dispatch import receiver

from .compat import get_languages, get_supported_language_variant


def find_available_slug(parent, requested_slug):
    existing_slugs = set(
        parent.get_children()
        .filter(slug__startswith=requested_slug)
        .values_list("slug", flat=True)
    )
    slug = requested_slug
    number = 1

    while slug in existing_slugs:
        slug = requested_slug + "-" + str(number)
        number += 1

    return slug


@functools.lru_cache(maxsize=1000)
def get_fallback_languages(lang_code):
    """
    Returns a list of language codes that can be used as a fallback to the given language
    """
    possible_lang_codes = []

    # Check if this is a special-case
    try:
        possible_lang_codes.extend(LANG_INFO[lang_code]["fallback"])
    except (KeyError, IndexError):
        pass

    # Convert region specific language codes into generic (eg fr-ca => fr)
    generic_lang_code = lang_code.split("-")[0]
    supported_lang_codes = get_languages()

    possible_lang_codes.append(generic_lang_code)

    # Try other regions with the same language
    for supported_code in supported_lang_codes:
        if supported_code.startswith(generic_lang_code + "-"):
            possible_lang_codes.append(supported_code)

    # Finally try the default language
    possible_lang_codes.append(get_supported_language_variant(settings.LANGUAGE_CODE))

    # Remove lang_code and any duplicates
    seen = {lang_code}
    deduplicated_lang_codes = []
    for possible_lang_code in possible_lang_codes:
        if possible_lang_code not in seen:
            deduplicated_lang_codes.append(possible_lang_code)
            seen.add(possible_lang_code)

    return deduplicated_lang_codes


@receiver(setting_changed)
def reset_cache(**kwargs):
    """
    Clear cache when global LANGUAGES/LANGUAGE_CODE settings are changed
    """
    if kwargs["setting"] in ("LANGUAGES", "LANGUAGE_CODE"):
        get_fallback_languages.cache_clear()
