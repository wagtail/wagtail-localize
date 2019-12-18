# Generated by Django 2.2.5 on 2019-09-03 14:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_localize", "0002_initial_data"),
        ("wagtail_localize_pontoon", "0003_synclog"),
    ]

    operations = [
        migrations.CreateModel(
            name="PontoonSyncLogResource",
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
                    "language",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="wagtail_localize.Language",
                    ),
                ),
                (
                    "log",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resources",
                        to="wagtail_localize_pontoon.PontoonSyncLog",
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="wagtail_localize_pontoon.PontoonResource",
                    ),
                ),
            ],
        )
    ]