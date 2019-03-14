import uuid

from django.core.management.base import BaseCommand, CommandError

from wagtail_i18n.models import BootstrapTranslatable, get_translatable_models


class Command(BaseCommand):
    help = 'Populates require fields of new translatable models'

    def handle(self, **options):
        for model in get_translatable_models():
            if issubclass(model, BootstrapTranslatable):
                print("Bootstrapping: {}.{}".format(model._meta.app_label, model.__name__))

                # TODO: Optimise for databases that have a UUID4 function
                for instance in model.objects.filter(translation_key__isnull=True).defer().iterator():
                    instance.translation_key = uuid.uuid4()
                    instance.save(update_fields=['translation_key'])
