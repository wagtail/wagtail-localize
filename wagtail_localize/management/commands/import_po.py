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


def yield_locales(locales):
    default = default_locale_id()
    splitter = defaultdict(list)
    for locale in locales:
        splitter[locale.id == default].append(locale)
    try:
        pot_locale = splitter[True]
    except KeyError:
        raise ValueError("No default language set")

    po_locales = splitter.get(False, [])
    for locale in po_locales:
        yield (pot_locale, locale)


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
    help = "Export .po files for all locals"

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
            '--po-fmt', dest='po_outfmt', default=po_outfmt, type=str
        )

        parser.add_argument(
            '--publish',
            dest='publish',
            action='store_const',
            const=True,
            default=False,
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
        locales = Locale.objects.filter(is_active=True)

        publish = options.get('publish', False)

        root_page = site.root_page if site else None
        if root_page is None:
            raise ValueError("Site is not properly configured, no root page.")

        for source_locale, target_locale in yield_locales(locales):
            print("Loading translations for {}".format(target_locale))
            translations = LocaleLoader(target_locale, options)
            message_ingestor = MessageIngestor(
                source_locale, target_locale, translations.items,
            )

            for page in get_pages(root_page):
                instance = page.get_latest_revision().as_page_object()
                translation = message_ingestor.ingest_messages(instance)
                if publish:
                    translation.get_latest_revision().publish()
