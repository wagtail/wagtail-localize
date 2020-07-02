from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ObjectDoesNotExist

from wagtail_localize.translation.models import TranslatableObject


class Command(BaseCommand):
    help = "Updates the paths of all translatable objects"

    def handle(self, **options):
        # TODO: Handle case where a path is changed to an existing path, but that
        # existing user of that path has changed to something else.
        # There may be a brief moment where they both use the same path.
        for object in TranslatableObject.objects.all():
            old_path = object.path

            try:
                object.path = TranslatableObject.get_path(object.get_source_instance())
            except ObjectDoesNotExist:
                # Source has been deleted
                # Change path to something that won't clash with other objects
                object.path = 'deleted/' + str(object.translation_key)

            if object.path != old_path:
                print("Updating path for", str(object.translation_key), "from", old_path, "to", object.path)
                object.save(update_fields=['path'])
