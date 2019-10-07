from collections import OrderedDict

import polib
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from wagtail_localize.models import Language

from wagtail_localize.translation_memory.translation_ingestor import ingest_translations


class Command(BaseCommand):
    def handle(self, **options):
        src_lang = Language.default()
        tgt_lang = Language.objects.filter(code="fr").first()

        po = polib.pofile("site-fr.po")
        translations = [(message.msgid, message.msgstr) for message in po]
        ingest_translations(src_lang, tgt_lang, translations)
