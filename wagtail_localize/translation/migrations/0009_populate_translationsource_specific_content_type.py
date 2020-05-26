# Generated by Django 3.0.6 on 2020-06-24 21:55

from django.db import migrations


def populate_specific_content_type(apps, schema_editor):
    TranslationSource = apps.get_model('wagtail_localize_translation.TranslationSource')

    # Initialise specific_content_type to object.content_type. While this is technically incorrect,
    # Wagtail localize is only used by one project at the moment so this is fine.
    for source in TranslationSource.objects.only('object'):
        source.specific_content_type_id = source.object.content_type_id
        source.save(update_fields=['specific_content_type_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('wagtail_localize_translation', '0008_translationsource_specific_content_type'),
    ]

    operations = [
        migrations.RunPython(populate_specific_content_type, migrations.RunPython.noop),
    ]