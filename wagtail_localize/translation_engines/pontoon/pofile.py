import polib
from django.utils import timezone


def generate_source_pofile(resource):
    """
    Generate a source PO file for the given resource
    """
    po = polib.POFile(wrapwidth=200)
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/html; charset=utf-8",
    }

    for segment in (
        resource.get_segments().select_related("segment", "context").iterator()
    ):
        po.append(
            polib.POEntry(
                msgid=segment.segment.text,
                msgstr="",
                msgctxt=segment.context.as_string(),
            )
        )

    return str(po)


def generate_language_pofile(resource, language):
    """
    Generate a translated PO file for the given resource/language
    """
    po = polib.POFile(wrapwidth=200)
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/html; charset=utf-8",
        "Language": language.as_rfc5646_language_tag(),
    }

    # Live segments
    for segment in (
        resource.get_segments()
        .select_related("segment", "context")
        .annotate_translation(language)
        .iterator()
    ):
        po.append(
            polib.POEntry(
                msgid=segment.segment.text,
                msgstr=segment.translation or "",
                msgctxt=segment.context.as_string(),
            )
        )

    # Add any obsolete segments that have translations for future reference
    # We find this by looking for obsolete contexts and annotate the latest
    # translation for each one. Contexts that were never translated are
    # excluded
    for translation in (
        resource.get_obsolete_translations(language)
        .select_related("translation_of", "context")
        .filter(context__isnull=False)
        .iterator()
    ):
        po.append(
            polib.POEntry(
                msgid=translation.translation_of.text,
                msgstr=translation.text or "",
                msgctxt=translation.context.as_string(),
                obsolete=True,
            )
        )

    return str(po)
