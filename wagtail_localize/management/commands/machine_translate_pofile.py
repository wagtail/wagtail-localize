from pathlib import Path

import polib
from django.core.management.base import BaseCommand

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.strings import StringValue


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('source_language_code', type=str)
        parser.add_argument('target_language_code', type=str)
        parser.add_argument('pofile', type=Path)

    def handle(self, source_language_code, target_language_code, pofile, **options):
        po = polib.pofile(str(pofile))

        messages = set(StringValue(entry.msgid) for entry in po)

        translator = get_machine_translator()
        translations = translator.translate(source_language_code, target_language_code, list(messages))

        new_po = polib.POFile()

        for entry in po:
            entry.msgstr = translations[StringValue(entry.msgid)].data
            new_po.append(entry)

        print(str(new_po))
