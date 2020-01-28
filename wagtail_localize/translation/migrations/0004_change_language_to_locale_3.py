# Generated by Django 2.2.9 on 2020-01-28 17:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_localize", "0002_initial_data"),
        ("wagtail_localize_translation", "0003_change_language_to_locale_2"),
    ]

    operations = [
        migrations.AlterField(
            model_name="segment",
            name="locale",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="wagtail_localize.Locale",
            ),
        ),
        migrations.AlterField(
            model_name="segmenttranslation",
            name="locale",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="wagtail_localize.Locale",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="segment", unique_together={("locale", "text_id")},
        ),
        migrations.AlterUniqueTogether(
            name="segmenttranslation",
            unique_together={("locale", "translation_of", "context")},
        ),
        migrations.RemoveField(model_name="segment", name="language",),
        migrations.RemoveField(model_name="segmenttranslation", name="language",),
    ]
