from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from wagtail_localize.models import Language


class Command(BaseCommand):
    help = "Synchronises the value of settings.LANGUAGES with the Language model"

    def handle(self, **options):
        language_codes = dict(settings.LANGUAGES).keys()

        for language_code in language_codes:
            Language.objects.update_or_create(
                code=language_code, defaults={"is_active": True}
            )

        for deactivated_languages in Language.objects.exclude(
            code__in=language_codes
        ).filter(is_active=True):
            deactivated_languages.is_active = False
            deactivated_languages.save()
