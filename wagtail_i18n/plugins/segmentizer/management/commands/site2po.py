from collections import OrderedDict

import polib
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from wagtail_i18n.models import get_translatable_models, Language, Locale, Region
from wagtail_i18n.plugins.segmentizer.models import TextSegment, TextSegmentPageLocation, HTMLSegmentPageLocation
from wagtail_i18n.plugins.segmentizer.segmentizer import segmentize


class Command(BaseCommand):

    def handle(self, **options):
        src_locale = Locale.default()
        tgt_locale = Locale.objects.get(language=Language.objects.filter(code='fr').first(), region=Region.default())
        messages = OrderedDict()

        def get_page_revision(page):
            if page.live_revision:
                return page.live_revision

            latest_revision = page.get_latest_revision()
            if latest_revision:
                return latest_revision

            return page.save_revision(changed=False)

        def add_text_segment(text_segment):
            text = text_segment.text_segment
            if text not in messages:
                messages[text] = []

            messages[text].append((text_segment.page_revision.page.url_path, text_segment.path))

        def add_html_segment(html_segment):
            for text_segment in html_segment.html_segment.text_segments.all():
                text = text_segment.text_segment

                if text not in messages:
                    messages[text] = []
                    messages[text].append((html_segment.page_revision.page.url_path, html_segment.path + ':' + str(text_segment.position)))

        for model in get_translatable_models():
            if not issubclass(model, Page):
                continue

            if model._meta.abstract:
                continue

            content_type = ContentType.objects.get_for_model(model)
            pages = model.objects.live().filter(content_type=content_type, locale=src_locale)

            for page in pages:
                for segment in segmentize(page):
                    if segment.html:
                        add_html_segment(HTMLSegmentPageLocation.from_segment_value(get_page_revision(page), segment))
                    else:
                        add_text_segment(TextSegmentPageLocation.from_segment_value(get_page_revision(page), segment))

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

        for text_segment, occurances in messages.items():
            existing_translation = ''
            if tgt_locale:
                translation = TextSegment.objects.filter(translation_of=text_segment, locale=tgt_locale).first()

                if translation:
                    existing_translation = translation.text

            po.append(
                polib.POEntry(
                    msgid=text_segment.text,
                    msgstr=existing_translation,
                    occurrences=occurances
                )
            )

        po.save('site.po')
