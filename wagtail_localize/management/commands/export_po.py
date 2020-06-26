import pathlib

import polib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from wagtail.core.models import Site

from wagtail_localize.models import Locale, default_locale_id
from wagtail_localize.workflow.views.translate import MessageExtractor


def create_pofile():
    po = polib.POFile()
    po.metadata = {
        "POT-Creation-Date": str(timezone.now()),
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
    }
    return po


class LocaleDumper:
    def __init__(self, locale, is_default, options):
        self.locale = locale
        self.is_default = is_default
        self.options = options
        self.outfile = create_pofile()
        self.items = {}
        if not self.is_default and self.exists:
            infile = polib.pofile(self.filename, encoding='utf-8')
            self.items = {entry.msgid: entry.msgstr for entry in infile}

    @property
    def filename(self):
        if self.is_default:
            return self.options.get('pot_out')
        return self.options.get('po_outfmt').format(
            language_code=self.locale.language_code
        )

    @property
    def exists(self):
        return pathlib.Path(self.filename).exists()

    def append(self, msgid, occurances):
        self.outfile.append(
            polib.POEntry(
                msgid=msgid,
                msgstr=self.items.get(msgid, ''),
                occurrences=occurances,
            )
        )

    def ensure_path_exists(self):
        pathout = pathlib.Path(self.filename)
        if pathout.exists():
            if pathout.is_dir():
                raise ValueError(
                    "Invalid path for outfmt, file {} point to a directory"
                    "".format(pathout.parent)
                )
            pathout.parent.mkdir(parents=True, exist_ok=True)
        else:
            if pathout.parent.is_file():
                raise ValueError(
                    "Invalid path for outfmt, {} is a file, not a dir"
                    "".format(pathout.parent)
                )
            pathout.parent.mkdir(parents=True, exist_ok=True)

    def save(self):
        self.ensure_path_exists()
        self.outfile.save(self.filename)


def get_pages(page):
    """Recursively browse, export a page and yield its sub pages."""
    yield page
    for child in page.get_children():
        for sub in get_pages(child):
            yield sub


class Command(BaseCommand):
    help = "Export .po files for all locals"

    def add_arguments(self, parser):
        potfile = './locales/' + settings.WAGTAIL_SITE_NAME + '.pot'
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
            '--pot-locale',
            dest='pot_locale',
            type=str,
            help="Override the defaut locale to force the pivot language used"
            "to generate the .pot file",
        )
        parser.add_argument('--pot', dest='pot_out', default=potfile, type=str)
        parser.add_argument(
            '--po-fmt', dest='po_outfmt', default=po_outfmt, type=str
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

        pot_locale = options.get('pot_locale')
        if pot_locale:
            source_locale = Locale.objects.get(language_code=pot_locale)
        else:
            source_locale = Locale.objects.get(id=default_locale_id())

        root_page = site.root_page if site else None
        if root_page is None:
            raise ValueError("Site is not properly configured, no root page.")

        for locale in locales:

            dumper = LocaleDumper(
                locale, locale.id == source_locale.id, options
            )
            message_extractor = MessageExtractor(locale=locale)

            for page in get_pages(root_page):
                print("Dumping {} for locale {}".format(page, locale))
                instance = page.get_latest_revision().as_page_object()
                message_extractor.extract_messages(instance)

            for text, occurances in message_extractor.messages.items():
                dumper.append(text, occurances)

            print("Writing {}".format(dumper.filename))
            dumper.save()
