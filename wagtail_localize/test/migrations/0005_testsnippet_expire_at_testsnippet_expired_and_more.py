# Generated by Django 4.2.9 on 2024-01-06 13:20

import uuid

import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wagtailcore", "0077_alter_revision_user"),
        ("wagtail_localize_test", "0004_testparentalsnippet"),
    ]

    operations = [
        migrations.AddField(
            model_name="testsnippet",
            name="expire_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="expiry date/time"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="expired",
            field=models.BooleanField(
                default=False, editable=False, verbose_name="expired"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="first_published_at",
            field=models.DateTimeField(
                blank=True, db_index=True, null=True, verbose_name="first published at"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="go_live_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="go live date/time"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="has_unpublished_changes",
            field=models.BooleanField(
                default=False, editable=False, verbose_name="has unpublished changes"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="last_published_at",
            field=models.DateTimeField(
                editable=False, null=True, verbose_name="last published at"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="latest_revision",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailcore.revision",
                verbose_name="latest revision",
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="live",
            field=models.BooleanField(
                default=True, editable=False, verbose_name="live"
            ),
        ),
        migrations.AddField(
            model_name="testsnippet",
            name="live_revision",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailcore.revision",
                verbose_name="live revision",
            ),
        ),
        migrations.CreateModel(
            name="TestNoDraftModel",
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
                    "translation_key",
                    models.UUIDField(default=uuid.uuid4, editable=False),
                ),
                ("field", models.CharField(blank=True, max_length=10)),
                (
                    "locale",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="wagtailcore.locale",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "unique_together": {("translation_key", "locale")},
            },
        ),
    ]
