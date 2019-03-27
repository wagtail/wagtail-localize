import uuid

from django.db import models, transaction

from wagtail_i18n.segment_formatters import get_segment_formatter_class


class Segment(models.Model):
    UUID_NAMESPACE = uuid.UUID('59ed7d1c-7eb5-45fa-9c8b-7a7057ed56d7')

    locale = models.ForeignKey('wagtail_i18n.Locale', on_delete=models.CASCADE)
    uuid = models.UUIDField(unique=True)
    text = models.TextField()

    @classmethod
    def from_text(cls, locale, text):
        segment, created = cls.objects.get_or_create(
            locale=locale,
            uuid=uuid.uuid5(cls.UUID_NAMESPACE, text),
            defaults={
                'text': text,
            }
        )

        return segment


class SegmentTranslation(models.Model):
    translation_of = models.ForeignKey(Segment, on_delete=models.CASCADE, related_name='translations')
    locale = models.ForeignKey('wagtail_i18n.Locale', on_delete=models.CASCADE)
    text = models.TextField()

    class Meta:
        unique_together = [
            ('locale', 'translation_of'),
        ]

    @classmethod
    def from_text(cls, translation_of, locale, text):
        segment, created = cls.objects.get_or_create(
            translation_of=translation_of,
            locale=locale,
            defaults={
                'text': text,
            }
        )

        return segment


class Template(models.Model):
    BASE_UUID_NAMESPACE = uuid.UUID('4599eabc-3f8e-41a9-be61-95417d26a8cd')

    uuid = models.UUIDField(unique=True)
    template = models.TextField()
    template_format = models.CharField(max_length=100)

    @classmethod
    def from_segment_value(cls, locale, segment_value):
        formatter = get_segment_formatter_class(segment_value.format)()
        uuid_namespace = uuid.uuid5(cls.BASE_UUID_NAMESPACE, segment_value.format)

        segment_uuid = uuid.uuid5(uuid_namespace, segment_value.text)

        try:
            return cls.objects.get(uuid=segment_uuid)
        except Template.DoesNotExist:
            pass

        segment_texts = []
        def emit_segment(text):
            position = len(segment_texts)
            segment_texts.append((position, text))
            return position

        template_value = formatter.parse(segment_value.text, emit_segment)

        with transaction.atomic():
            template = Template.objects.create(
                uuid=segment_uuid,
                template=template_value,
            )

            for position, text in segment_texts:
                segment = Segment.from_text(locale, text)
                TemplateSegment.objects.create(
                    template=template,
                    position=position,
                    segment=segment,
                )

        return template

    def get_translated_content(self, locale):
        formatter = get_segment_formatter_class(segment_value.format)()

        # Note: this method is reliant on text segment translations being prefetched
        texts = {
            segment.position: segment.translation
            for segment in self.segments.all()
        }

        if texts:
            return formatter.render(self.template, texts)
        else:
            # There are no translatable snippets in the template
            return self.template


class TemplateSegment(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='segments')
    position = models.IntegerField()
    segment = models.ForeignKey(Segment, on_delete=models.PROTECT, related_name='+')


class BasePageLocation(models.Model):
    page_revision = models.ForeignKey('wagtailcore.PageRevision', on_delete=models.CASCADE)
    path = models.TextField()

    class Meta:
        abstract = True


class SegmentPageLocation(BasePageLocation):
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE, related_name='page_locations')

    @classmethod
    def from_segment_value(cls, page_revision, segment_value):
        segment = Segment.from_text(page_revision.page.locale, segment_value.text)

        segment_page_loc, created = cls.objects.get_or_create(
            page_revision=page_revision,
            path=segment_value.path,
            segment=segment,
        )

        return segment_page_loc


class TemplatePageLocation(BasePageLocation):
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='page_locations')

    @classmethod
    def from_segment_value(cls, page_revision, segment_value):
        template = Template.from_segment_value(page_revision.page.locale, segment_value)

        segment_page_loc, created = cls.objects.get_or_create(
            page_revision=page_revision,
            path=segment_value.path,
            template=template,
        )

        return segment_page_loc
