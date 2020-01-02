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

    for segment in resource.get_segments().iterator():
        po.append(polib.POEntry(msgid=segment.text, msgstr=""))

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
    for segment in resource.get_segments().annotate_translation(language).iterator():
        po.append(polib.POEntry(msgid=segment.text, msgstr=segment.translation or ""))

    # Add any obsolete segments that have translations for future referene
    for segment in (
        resource.get_all_segments(annotate_obsolete=True)
        .annotate_translation(language)
        .filter(is_obsolete=True, translation__isnull=False)
        .iterator()
    ):
        po.append(
            polib.POEntry(
                msgid=segment.text, msgstr=segment.translation or "", obsolete=True
            )
        )

    return str(po)
