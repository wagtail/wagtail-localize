# Generated by Django 3.1.3 on 2020-11-04 20:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0059_apply_collection_ordering"),
        ("wagtail_localize_test", "0007_auto_20201020_1410"),
    ]

    operations = [
        migrations.CreateModel(
            name="FlagLocaleComponent",
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
                (
                    "flag",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("union-jack", "Union Jack"),
                            ("tricolore", "Tricolore"),
                        ],
                        max_length=255,
                    ),
                ),
                (
                    "locale",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flag",
                        to="wagtailcore.locale",
                    ),
                ),
            ],
        ),
    ]
