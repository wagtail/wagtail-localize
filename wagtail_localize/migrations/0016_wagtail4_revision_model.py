import django.core.validators
from django.db import migrations, models

from wagtail import VERSION as WAGTAIL_VERSION


if WAGTAIL_VERSION >= (4, 0):
    # Wagtail 4.0 changed to using a more generic revision model, so if running
    # on it, migrate the TranslationLog.page_revision FK to the new model.
    # Note: if someone upgrades to this version of wagtail-localize while on Wagtail < 4.0,
    # they may need to re-run this migration after upgrading to Wagtail 4.0.
    class Migration(migrations.Migration):

        dependencies = [
            ("wagtail_localize", "0015_translationcontext_field_path"),
            ("wagtailcore", "0076_modellogentry_revision"),
        ]

        operations = [
            migrations.AlterField(
                model_name="TranslationLog",
                name="page_revision",
                field=models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="wagtailcore.Revision",
                ),
            )
        ]

else:

    class Migration(migrations.Migration):

        dependencies = [("wagtail_localize", "0015_translationcontext_field_path")]

        operations = []
