from django.core.management.base import BaseCommand, CommandError
from wagtail.core.models import Page

from wagtail_localize.models import Locale
from wagtail_localize.synctree import PageIndex, synchronize_tree


class Command(BaseCommand):
    help = "Synchronises the structure of all language page trees so they contain the same pages in the same position. Creates placeholder pages where necessary."

    def handle(self, **options):
        # Get an index of all pages
        index = PageIndex.from_database().sort_by_tree_position()

        for locale in Locale.objects.filter(is_active=True):
            synchronize_tree(index, locale)
