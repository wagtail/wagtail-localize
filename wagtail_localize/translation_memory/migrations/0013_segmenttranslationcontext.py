# Generated by Django 2.2.9 on 2019-12-31 15:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_localize", "0002_initial_data"),
        ("wagtail_localize_translation_memory", "0012_translationlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="SegmentTranslationContext",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("path_id", models.UUIDField()),
                ("path", models.TextField()),
                (
                    "object",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="wagtail_localize_translation_memory.TranslatableObject",
                    ),
                ),
            ],
            options={"unique_together": {("object", "path_id")},},
        ),
        migrations.AddField(
            model_name="relatedobjectlocation",
            name="context",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtail_localize_translation_memory.SegmentTranslationContext",
            ),
        ),
        migrations.AddField(
            model_name="segmentlocation",
            name="context",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtail_localize_translation_memory.SegmentTranslationContext",
            ),
        ),
        migrations.AddField(
            model_name="segmenttranslation",
            name="context",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="translations",
                to="wagtail_localize_translation_memory.SegmentTranslationContext",
            ),
        ),
        migrations.AddField(
            model_name="templatelocation",
            name="context",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtail_localize_translation_memory.SegmentTranslationContext",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="segmenttranslation",
            unique_together={("language", "translation_of", "context")},
        ),
    ]
