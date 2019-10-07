from collections import OrderedDict

import polib
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from wagtail_localize.models import get_translatable_models, Language
from wagtail_localize.translation_memory.models import (
    Segment,
    SegmentTranslation,
    SegmentPageLocation,
    TemplatePageLocation,
)
from wagtail_localize.translation_memory.utils import insert_segments
from wagtail_localize.segments import TemplateValue
from wagtail_localize.segments.extract import extract_segments


class Command(BaseCommand):
    def handle(self, **options):
        src_lang = Language.default()
        tgt_lang = Language.objects.filter(code="fr").first()
        messages = OrderedDict()

        def get_page_revision(page):
            if page.live_revision:
                return page.live_revision

            latest_revision = page.get_latest_revision()
            if latest_revision:
                return latest_revision

            return page.save_revision(changed=False)

        for model in get_translatable_models():
            if not issubclass(model, Page):
                continue

            if model._meta.abstract:
                continue

            content_type = ContentType.objects.get_for_model(model)
            pages = model.objects.live().filter(
                content_type=content_type, locale=src_lang
            )

            for page in pages:
                segments = extract_segments(page)
                insert_segments(get_page_revision(page), src_lang, segments)
                for segment in segments:
                    if not isinstance(segment, TemplateValue):
                        text = segment.html
                        if text not in messages:
                            messages[text] = []

                        messages[text].append((page.url_path, segment.path))

        po = polib.POFile()
        po.metadata = {
            "Project-Id-Version": "1.0",
            "Report-Msgid-Bugs-To": "you@example.com",
            "POT-Creation-Date": "2007-10-18 14:00+0100",
            "PO-Revision-Date": "2007-10-18 14:00+0100",
            "Last-Translator": "you <you@example.com>",
            "Language-Team": "English <yourteam@example.com>",
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Transfer-Encoding": "8bit",
        }

        for segment, occurances in messages.items():
            existing_translation = ""
            if tgt_lang:
                translation = SegmentTranslation.objects.filter(
                    translation_of__text=segment,
                    translation_of__locale=src_lang,
                    locale=tgt_lang,
                ).first()

                if translation:
                    existing_translation = translation.text

            po.append(
                polib.POEntry(
                    msgid=segment, msgstr=existing_translation, occurrences=occurances
                )
            )

        po.save("site.po")
