import uuid

from bs4 import BeautifulSoup
from django.db import models, transaction


class TextSegment(models.Model):
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


class TextSegmentTranslation(models.Model):
    translation_of = models.ForeignKey(TextSegment, on_delete=models.CASCADE, related_name='translations')
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


class HTMLSegment(models.Model):
    UUID_NAMESPACE = uuid.UUID('4599eabc-3f8e-41a9-be61-95417d26a8cd')

    uuid = models.UUIDField(unique=True)
    template = models.TextField()

    @classmethod
    def from_html(cls, locale, html):
        segment_uuid = uuid.uuid5(cls.UUID_NAMESPACE, html)

        try:
            return cls.objects.get(uuid=segment_uuid)
        except HTMLSegment.DoesNotExist:
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
            html_segment = HTMLSegment.objects.create(
                uuid=segment_uuid,
                template=str(soup),
            )

            for position, text in enumerate(texts):
                text_segment = TextSegment.from_text(locale, text)
                HTMLSegmentText.objects.create(
                    html_segment=html_segment,
                    position=position,
                    text_segment=text_segment,
                )

        return html_segment

    def get_translated_content(self, locale):
        # Note: this method is reliant on text segment translations being prefetched
        texts = {
            text_segment.position: text_segment.translation
            for text_segment in self.text_segments.all()
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


class HTMLSegmentText(models.Model):
    html_segment = models.ForeignKey(HTMLSegment, on_delete=models.CASCADE, related_name='text_segments')
    position = models.IntegerField()
    text_segment = models.ForeignKey(TextSegment, on_delete=models.PROTECT, related_name='+')


class BaseSegmentPageLocation(models.Model):
    page_revision = models.ForeignKey('wagtailcore.PageRevision', on_delete=models.CASCADE)
    path = models.TextField()

    class Meta:
        abstract = True


class TextSegmentPageLocation(BaseSegmentPageLocation):
    text_segment = models.ForeignKey(TextSegment, on_delete=models.CASCADE, related_name='page_locations')

    @classmethod
    def from_segment_value(cls, page_revision, segment_value):
        text_segment = TextSegment.from_text(page_revision.page.locale, segment_value.text)

        segment_page_loc, created = cls.objects.get_or_create(
            page_revision=page_revision,
            path=segment_value.path,
            text_segment=text_segment,
        )

        return segment_page_loc


class HTMLSegmentPageLocation(BaseSegmentPageLocation):
    html_segment = models.ForeignKey(HTMLSegment, on_delete=models.CASCADE, related_name='page_locations')

    @classmethod
    def from_segment_value(cls, page_revision, segment_value):
        html_segment = HTMLSegment.from_html(page_revision.page.locale, segment_value.text)

        segment_page_loc, created = cls.objects.get_or_create(
            page_revision=page_revision,
            path=segment_value.path,
            html_segment=html_segment,
        )

        return segment_page_loc
