# Generated by Django 2.2.9 on 2019-12-31 16:30

import uuid
from django.db import migrations


def get_path_id(path):
    return uuid.uuid5(uuid.UUID("fcab004a-2b50-11ea-978f-2e728ce88125"), path)


def populate_segmenttranslationcontext(apps, schema_editor):
    SegmentLocation = apps.get_model(
        "wagtail_localize_translation_memory.SegmentLocation"
    )
    TemplateLocation = apps.get_model(
        "wagtail_localize_translation_memory.TemplateLocation"
    )
    RelatedObjectLocation = apps.get_model(
        "wagtail_localize_translation_memory.RelatedObjectLocation"
    )
    SegmentTranslation = apps.get_model(
        "wagtail_localize_translation_memory.SegmentTranslation"
    )
    SegmentTranslationContext = apps.get_model(
        "wagtail_localize_translation_memory.SegmentTranslationContext"
    )

    def update_location_model(model):
        for location in model.objects.select_related("revision"):
            context, created = SegmentTranslationContext.objects.get_or_create(
                object_id=location.revision.object_id,
                path_id=get_path_id(location.path),
                defaults={"path": location.path,},
            )

            location.context = context
            location.save(update_fields=["context"])

    update_location_model(SegmentLocation)
    update_location_model(TemplateLocation)
    update_location_model(RelatedObjectLocation)

    for translation in SegmentTranslation.objects.all():
        contexts = (
            SegmentLocation.objects.filter(segment_id=translation.translation_of_id)
            .order_by("context_id")
            .values_list("context_id", flat=True)
            .distinct()
        )

        if len(contexts) > 0:
            translation.context_id = contexts[0]
            translation.save(update_fields=["context_id"])

        # Create duplicate SegmentTranslations for remaining contexts
        if len(contexts) > 1:
            for context in contexts[1:]:
                SegmentTranslation.objects.create(
                    translation_of_id=translation.translation_of_id,
                    language_id=translation.language_id,
                    context_id=context,
                    text=translation.text,
                    created_at=translation.created_at,
                    updated_at=translation.updated_at,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_localize_translation_memory", "0013_segmenttranslationcontext"),
    ]

    operations = [
        migrations.RunPython(populate_segmenttranslationcontext),
    ]
