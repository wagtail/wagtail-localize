from django.core.management.base import BaseCommand

from wagtail_localize.models import LocaleSynchronization
from wagtail_localize.synctree import PageIndex


class Command(BaseCommand):
    help = "Synchronises the structure of all locale page trees so they contain the same pages. Creates alias pages where necessary."

    def handle(self, **options):
        page_index = PageIndex.from_database().sort_by_tree_position()
        for locale_sync in LocaleSynchronization.objects.all():
            locale_sync.sync_trees(page_index=page_index)
