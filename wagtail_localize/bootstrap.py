import uuid

from django.conf import settings
from django.db import migrations

from .compat import get_supported_language_variant


def bootstrap_translatable_model(model, locale):
    """
    This function populates the "translation_key", and "locale" fields on model instances that were created
    before wagtail-localize was added to the site.

    This can be called from a data migration, or instead you could use the "boostrap_translatable_models"
    management command.
    """
    # TODO: Optimise for databases that have a UUID4 function
    for instance in (
        model.objects.filter(translation_key__isnull=True).defer().iterator()
    ):
        instance.translation_key = uuid.uuid4()
        instance.locale = locale
        instance.save(update_fields=["translation_key", "locale"])


class BootstrapTranslatableModel(migrations.RunPython):
    def __init__(self, model_string, language_code=None, region_slug="default"):
        def forwards(apps, schema_editor):
            model = apps.get_model(model_string)
            Locale = apps.get_model("wagtail_localize.Locale")

            if language_code is not None:
                locale = Locale.objects.get(
                    language__code=language_code, region__slug=region_slug
                )
            else:
                locale = Locale.objects.default()

            bootstrap_translatable_model(model, locale)

        def backwards(apps, schema_editor):
            pass

        super().__init__(forwards, backwards)
