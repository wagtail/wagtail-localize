import uuid

from bs4 import BeautifulSoup
from django.db import models, transaction


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


class HTMLTemplate(models.Model):
    UUID_NAMESPACE = uuid.UUID('4599eabc-3f8e-41a9-be61-95417d26a8cd')

    uuid = models.UUIDField(unique=True)
    template = models.TextField()

    @classmethod
    def from_html(cls, locale, html):
        segment_uuid = uuid.uuid5(cls.UUID_NAMESPACE, html)

        try:
            return cls.objects.get(uuid=segment_uuid)
        except HTMLTemplate.DoesNotExist:
            pass

        soup = BeautifulSoup(html, 'html.parser')
        texts = []

        for descendant in soup.descendants:
            if descendant.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
                string = descendant.string

                if string:
                    position = len(texts)
                    texts.append(descendant.string)
                    descendant.clear()
                    descendant.append(soup.new_tag('text', position=position))

        with transaction.atomic():
            html_template = HTMLTemplate.objects.create(
                uuid=segment_uuid,
                template=str(soup),
            )

            for position, text in enumerate(texts):
                segment = Segment.from_text(locale, text)
                HTMLTemplateSegment.objects.create(
                    html_template=html_template,
                    position=position,
                    segment=segment,
                )

        return html_template

    def get_translated_content(self, locale):
        # Note: this method is reliant on text segment translations being prefetched
        texts = {
            segment.position: segment.translation
            for segment in self.segments.all()
        }

        if texts:
            soup = BeautifulSoup(self.template, 'html.parser')

            for text_element in soup.findAll('text'):
                value = texts[int(text_element.get('position'))]
                text_element.replaceWith(value)

            return str(soup)

        else:
            # There are no translatable snippets in the HTML
            return self.template


class HTMLTemplateSegment(models.Model):
    html_template = models.ForeignKey(HTMLTemplate, on_delete=models.CASCADE, related_name='segments')
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


class HTMLTemplatePageLocation(BasePageLocation):
    html_template = models.ForeignKey(HTMLTemplate, on_delete=models.CASCADE, related_name='page_locations')

    @classmethod
    def from_segment_value(cls, page_revision, segment_value):
        html_template = HTMLTemplate.from_html(page_revision.page.locale, segment_value.text)

        segment_page_loc, created = cls.objects.get_or_create(
            page_revision=page_revision,
            path=segment_value.path,
            html_template=html_template,
        )

        return segment_page_loc
