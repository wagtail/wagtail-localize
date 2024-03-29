# Generated by Django 3.0.8 on 2020-08-12 18:34

import django.db.models.deletion

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("wagtail_localize", "0007_stringtranslation_type_and_tool_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="stringtranslation",
            name="last_translated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
