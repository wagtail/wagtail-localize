import uuid

from django.db import migrations


def bootstrap_translatable_model(model):
    """
    This function populates the "translation_key" field on model instances that were created
    before wagtail-i18n was added to the site.

    This can be called from a data migration, or instead you could use the "boostrap_translatable_models"
    management command.
    """
    # TODO: Optimise for databases that have a UUID4 function
    for instance in model.objects.filter(translation_key__isnull=True).defer().iterator():
        instance.translation_key = uuid.uuid4()
        instance.save(update_fields=['translation_key'])


class BootstrapTranslatableModel(migrations.RunPython):
    def __init__(self, model_string):
        def forwards(apps, schema_editor):
            model = apps.get_model(model_string)
            bootstrap_translatable_model(model)

        def backwards(apps, schema_editor):
            pass

        super().__init__(forwards, backwards)
