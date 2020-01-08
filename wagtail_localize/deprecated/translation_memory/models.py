from django.db import models


class Segment(models.Model):
    language = models.ForeignKey("wagtail_localize.Language", on_delete=models.CASCADE, related_name="+")
    text_id = models.UUIDField()
    text = models.TextField()

    class Meta:
        unique_together = [("language", "text_id")]


class SegmentTranslation(models.Model):
    translation_of = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="translations"
    )
    language = models.ForeignKey("wagtail_localize.Language", on_delete=models.CASCADE, related_name="+")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("language", "translation_of")]


class Template(models.Model):
    uuid = models.UUIDField(unique=True)
    template = models.TextField()
    template_format = models.CharField(max_length=100)
    segment_count = models.PositiveIntegerField()


class BasePageLocation(models.Model):
    page_revision = models.ForeignKey(
        "wagtailcore.PageRevision", on_delete=models.CASCADE, related_name="+"
    )
    path = models.TextField()
    order = models.PositiveIntegerField()

    class Meta:
        abstract = True


class SegmentPageLocation(BasePageLocation):
    segment = models.ForeignKey(
        Segment, on_delete=models.CASCADE, related_name="page_locations"
    )
    html_attrs = models.TextField(blank=True)


class TemplatePageLocation(BasePageLocation):
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="page_locations"
    )
