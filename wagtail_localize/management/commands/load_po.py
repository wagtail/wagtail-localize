import pathlib
from collections import defaultdict

import polib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from wagtail.core.models import Site

from wagtail_localize.models import Locale, default_locale_id
from wagtail_localize.workflow.views.translate import MessageIngestor


class LocaleLoader:
    def __init__(self, locale, options):
        self.locale = locale
        self.options = options
        self.items = {}
        if self.exists:
            infile = polib.pofile(self.filename, encoding='utf-8')
            self.items = {
                entry.msgid: entry.msgstr or entry.msgid for entry in infile
            }

    @property
    def filename(self):
        return self.options.get('po_outfmt').format(
            language_code=self.locale.language_code
        )

    @property
    def exists(self):
        return pathlib.Path(self.filename).exists


def get_pages(page):
    """Recursively browse, export a page and yield its sub pages."""
    yield page
    for child in page.get_children():
        for sub in get_pages(child):
            yield sub


class CommandHandler:
    def __init__(self, site, potfile, po_outfmt):
        page = site.root_page


class Command(BaseCommand):
    help = "Dump all translatable translations for a webside .po files for "
    "its all locals"

    def add_arguments(self, parser):
        po_outfmt = (
            './locales/{language_code}/LC_MESSAGES/'
            + settings.WAGTAIL_SITE_NAME
            + '.po'
        )
        parser.add_argument(
            '--site',
            dest='site',
            type=str,
            help="host:port of the site, the default site will be exported "
            "if not specified",
        )
        parser.add_argument(
            '--po-fmt', dest='po_outfmt', default=po_outfmt, type=str,
            help="Format for locales .po path"
        )
        parser.add_argument(
            '--pot-locale',
            dest='pot_locale',
            type=str,
            help="Override the defaut locale to force the pivot language used"
            "while generating the .pot file",
        )

        parser.add_argument(
            '--publish',
            dest='publish',
            action='store_const',
            const=True,
            default=False,
            help="Publish pages after loading translations, draft by default"
        )

    def handle(self, **options):

        if options.get('site'):
            host_port = option.get('split').rsplit(':', maxsplit=1)
            site = Site.objects.filter(
                hostname=host_port[0],
                port=int(host_port[1]) if len(host_port) == 2 else 80,
            ).first()
        else:
            site = Site.objects.filter(is_default_site=True).first()

        pot_locale = options.get('pot_locale')
        if pot_locale:
            source_locale = Locale.objects.get(language_code=pot_locale)
        else:
            source_locale = Locale.objects.get(id=default_locale_id())

        locales = Locale.objects.filter(is_active=True).exclude(
            id=source_locale.id
        )

        publish = options.get('publish', False)

        root_page = site.root_page if site else None
        if root_page is None:
            raise ValueError("Site is not properly configured, no root page.")

        for target_locale in locales:
            print(
                "Loading translations for {} -> {}".format(
                    source_locale, target_locale
                )
            )
            translations = LocaleLoader(target_locale, options)
            message_ingestor = MessageIngestor(
                source_locale, target_locale, translations.items,
            )

            for page in get_pages(root_page):
                print("Loading page {}".format(page))
                instance = page.get_latest_revision().as_page_object()
                if instance.is_source_translation:
                    if instance.locale.id != source_locale.id:
                        print(
                            "Fix the locale for the source {} -> {}."
                            "".format(instance.locale, source_locale)
                        )
                        instance.locale = source_locale
                        instance.save()
                translation = message_ingestor.ingest_messages(instance)
                if publish:
                    translation.get_latest_revision().publish()
