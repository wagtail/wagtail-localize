from collections import OrderedDict

import polib
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from wagtail_i18n.models import Language, Locale, Region

from wagtail_i18n.plugins.segmentizer.translation_ingestor import ingest_translations


class Command(BaseCommand):

    def handle(self, **options):
        src_locale = Locale.default()
        tgt_locale = Locale.objects.get(language=Language.objects.filter(code='fr').first(), region=Region.default())

        po = polib.pofile('site-fr.po')
        translations = [(message.msgid, message.msgstr) for message in po]
        ingest_translations(src_locale, tgt_locale, translations)
