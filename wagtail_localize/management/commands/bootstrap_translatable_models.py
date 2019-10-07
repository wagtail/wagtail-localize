from django.core.management.base import BaseCommand, CommandError

from wagtail_localize.bootstrap import bootstrap_translatable_model
from wagtail_localize.models import BootstrapTranslatableMixin, get_translatable_models


class Command(BaseCommand):
    help = "Populates require fields of new translatable models"

    def handle(self, **options):
        for model in get_translatable_models():
            if issubclass(model, BootstrapTranslatableMixin):
                print(
                    "Bootstrapping: {}.{}".format(model._meta.app_label, model.__name__)
                )

                bootstrap_translatable_model(model)
