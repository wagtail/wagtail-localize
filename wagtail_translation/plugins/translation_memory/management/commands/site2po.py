from collections import OrderedDict

import polib
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from wagtail_translation.models import get_translatable_models, Language, Locale, Region
from wagtail_translation.plugins.translation_memory.models import Segment, SegmentTranslation, SegmentPageLocation, TemplatePageLocation
from wagtail_translation.segments import TemplateValue
from wagtail_translation.segments.extract import extract_segments


class Command(BaseCommand):

    def handle(self, **options):
        src_locale = Locale.default()
        tgt_locale = Locale.objects.get(language=Language.objects.filter(code='fr').first(), region=Region.objects.filter(slug='france').first())
        messages = OrderedDict()

        def get_page_revision(page):
            if page.live_revision:
                return page.live_revision

            latest_revision = page.get_latest_revision()
            if latest_revision:
                return latest_revision

            return page.save_revision(changed=False)

        def add_segment(page, segment):
            text = segment.text
            if text not in messages:
                messages[text] = []

            messages[text].append((page.url_path, segment.path))

        for model in get_translatable_models():
            if not issubclass(model, Page):
                continue

            if model._meta.abstract:
                continue

            content_type = ContentType.objects.get_for_model(model)
            pages = model.objects.live().filter(content_type=content_type, locale=src_locale)

            for page in pages:
                for segment in extract_segments(page):
                    if isinstance(segment, TemplateValue):
                        TemplatePageLocation.from_template_value(get_page_revision(page), segment)
                    else:
                        SegmentPageLocation.from_segment_value(get_page_revision(page), segment)
                        add_segment(page, segment)

        po = polib.POFile()
        po.metadata = {
            'Project-Id-Version': '1.0',
            'Report-Msgid-Bugs-To': 'you@example.com',
            'POT-Creation-Date': '2007-10-18 14:00+0100',
            'PO-Revision-Date': '2007-10-18 14:00+0100',
            'Last-Translator': 'you <you@example.com>',
            'Language-Team': 'English <yourteam@example.com>',
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Transfer-Encoding': '8bit',
        }

        for segment, occurances in messages.items():
            existing_translation = ''
            if tgt_locale:
                translation = SegmentTranslation.objects.filter(translation_of__text=segment, translation_of__locale=src_locale, locale=tgt_locale).first()

                if translation:
                    existing_translation = translation.text

            po.append(
                polib.POEntry(
                    msgid=segment,
                    msgstr=existing_translation,
                    occurrences=occurances
                )
            )

        po.save('site.po')
