# Generated by Django 3.0.6 on 2020-05-26 18:51

from django.db import migrations


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('wagtail_localize_translation', '0001_initial_squashed_0004_change_language_to_locale_3'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='SegmentTranslationContext',
            new_name='TranslationContext',
        ),
    ]
