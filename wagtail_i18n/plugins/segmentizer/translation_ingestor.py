from collections import defaultdict

from django.db import models, transaction
from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from wagtail.core import blocks
from wagtail.core.fields import StreamField
from wagtail.core.models import Page, PageRevision
from wagtail.core.rich_text import RichText
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

from wagtail_i18n.models import TranslatableMixin, Locale
from wagtail_i18n.segments import SegmentValue

from .models import TextSegment, TextSegmentPageLocation, HTMLSegmentPageLocation, HTMLSegmentText
from .utils import get_translation_progress


def handle_related_object(related_object, src_locale, tgt_locale, segments):
    if related_object is None or not isinstance(related_object, TranslatableMixin):
        return related_object

    # Note: when called from streamfield, we may be given the translated object
    related_original = related_object.get_translation(src_locale)
    related_translated = related_object.get_translation_or_none(tgt_locale)

    if related_translated is None:
        # Create translated version by copying the original version
        related_translated = related_original.copy_for_translation(tgt_locale)

    # Get segments by related field name
    segments_by_related_field_name = defaultdict(list)
    for segment in segments:
        related_field_name, segment = segment.unwrap()
        segments_by_related_field_name[related_field_name].append(segment)

    populate_translated_fields(related_original, related_translated, src_locale, tgt_locale, segments_by_related_field_name)
    related_translated.save()

    return related_translated


class StreamFieldSegmentsWriter:
    def __init__(self, field, src_locale, tgt_locale):
        self.field = field
        self.src_locale = src_locale
        self.tgt_locale = tgt_locale

    def handle_block(self, block_type, block_value, segments):
        if hasattr(block_type, 'restore_translated_segments'):
            return block_type.restore_translated_segments(block_value, segments)

        elif isinstance(block_type, blocks.CharBlock):
            return segments[0].text

        elif isinstance(block_type, blocks.RichTextBlock):
            return RichText(segments[0].text)

        elif isinstance(block_type, (ImageChooserBlock, SnippetChooserBlock)):
            return self.handle_related_object_block(block_value, segments)

        elif isinstance(block_type, blocks.StructBlock):
            return self.handle_struct_block(block_value, segments)

        elif isinstance(block_type, blocks.ListBlock):
            return self.handle_list_block(block_value, segments)

        else:
            raise Exception("Unrecognised StreamField block type '{}'. Have you implemented restore_translated_segments() on this class?".format(block_type.__class__.__name__))

    def handle_related_object_block(self, related_object, segments):
        return handle_related_object(related_object, self.src_locale, self.tgt_locale, segments)

    def handle_struct_block(self, struct_block, segments):
        segments_by_field = defaultdict(list)

        for segment in segments:
            field_name, segment = segment.unwrap()
            segments_by_field[field_name].append(segment)

        for field_name in getattr(struct_block.block.meta, 'translated_fields', []):
            segments = segments_by_field[field_name]

            if segments:
                block_type = struct_block.block.child_blocks[field_name]
                block_value = struct_block[field_name]
                struct_block[field_name] = self.handle_block(block_type, block_value, segments)

        return struct_block

    def handle_list_block(self, list_block, segments):
        # TODO
        pass

    def get_stream_block_child_data(self, data, block_uuid):
        for stream_child in data:
            if stream_child.id == block_uuid:
                return stream_child

    def handle_stream_block(self, data, segments):
        segments_by_block = defaultdict(list)

        for segment in segments:
            block_uuid, segment = segment.unwrap()
            segments_by_block[block_uuid].append(segment)

        for block_uuid, segments in segments_by_block.items():
            block = self.get_stream_block_child_data(data, block_uuid)
            block.value = self.handle_block(block.block, block.value, segments)


def populate_translated_fields(original_obj, translated_obj, src_locale, tgt_locale, segments_by_field_name):
    for field_name, segments in segments_by_field_name.items():
        field = translated_obj.__class__._meta.get_field(field_name)

        if isinstance(field, StreamField):
            data = field.value_from_object(translated_obj)
            StreamFieldSegmentsWriter(field, src_locale, tgt_locale).handle_stream_block(data, segments)
            setattr(translated_obj, field_name, data)

        elif isinstance(field, (models.TextField, models.CharField)):
            setattr(translated_obj, field_name, segments[0].text)

        elif isinstance(field, models.ForeignKey):
            related_original = getattr(original_obj, field_name)
            related_translated = handle_related_object(related_original, src_locale, tgt_locale, segments)
            setattr(translated_obj, field_name, related_translated)

        elif isinstance(field, (models.ManyToOneRel)):
            original_manager = getattr(original_obj, field_name)
            translated_manager = getattr(translated_obj, field_name)

            segments_by_child = defaultdict(list)

            for segment in segments:
                child_translation_key, segment = segment.unwrap()
                segments_by_child[child_translation_key].append(segment)

            for child_translation_key, segments in segments_by_child.items():
                original_child_object = original_manager.filter(translation_key=child_translation_key).first()
                translated_child_object = translated_manager.filter(translation_key=child_translation_key).first()

                if not translated_child_object:
                    # TODO: Here, we expect that the inline child to already exist as Wagtail copies it
                    # when creating the translated page. When we add editing, we will need to support
                    # adding new inline objects manually.
                    continue

                # Get segments by related field name
                segments_by_related_field_name = defaultdict(list)
                for segment in segments:
                    related_field_name, segment = segment.unwrap()
                    segments_by_related_field_name[related_field_name].append(segment)

                populate_translated_fields(original_child_object, translated_child_object, src_locale, tgt_locale, segments_by_related_field_name)
                translated_child_object.save()


@transaction.atomic
def handle_completed_revision(revision_id, src_locale, tgt_locale):
    original_page = Page.objects.get(revisions__id=revision_id).specific

    # TODO: Not currently handling edited page translations
    if original_page.has_translation(tgt_locale):
        return

    original_page_at_revision = original_page.revisions.get(id=revision_id).as_page_object()
    translated_page = original_page_at_revision.copy_for_translation(tgt_locale)

    # If the page doesn't yet have a translated parent, don't import it yet
    # This function will be called again when the translated parent is created
    if not translated_page:
        return

    # Fetch all translated segments
    text_segment_page_locations = (
        TextSegmentPageLocation.objects
        .filter(page_revision_id=revision_id)
        .annotate(
            translation=Subquery(
                TextSegment.objects.filter(
                    translation_of_id=OuterRef('text_segment_id'),
                    locale=tgt_locale,
                ).values('text')
            )
        )
    )

    html_segment_page_locations = (
        HTMLSegmentPageLocation.objects
        .filter(page_revision_id=revision_id)
        .select_related('html_segment')
        .prefetch_related(
            Prefetch(
                'html_segment__text_segments',
                queryset=(
                    HTMLSegmentText.objects
                    .annotate(
                        translation=Subquery(
                            TextSegment.objects.filter(
                                translation_of_id=OuterRef('text_segment_id'),
                                locale=tgt_locale,
                            ).values('text')
                        )
                    )
                )
            )
        )
    )

    segments_by_field_name = defaultdict(list)

    for page_location in text_segment_page_locations:
        segment = SegmentValue(page_location.path, page_location.translation)
        field_name, segment = segment.unwrap()
        segments_by_field_name[field_name].append(segment)

    for page_location in html_segment_page_locations:
        segment = SegmentValue(page_location.path, page_location.html_segment.get_translated_content(tgt_locale))
        field_name, segment = segment.unwrap()
        segments_by_field_name[field_name].append(segment)

    populate_translated_fields(original_page_at_revision, translated_page, src_locale, tgt_locale, segments_by_field_name)

    translated_page.slug = slugify(translated_page.slug)

    translated_page.save()

    # Create initial revision
    translated_page.save_revision(changed=False)

    # As we created a new page, check to see if there are any child pages that
    # have complete translations as well. This can happen if the child pages
    # were translated before the parent.

    # Check all page revisions of children of the original page that have
    # been submitted for localisation
    child_page_revision_ids = PageRevision.objects.filter(page__in=original_page.get_children()).values_list('id', flat=True)
    submitted_page_revision_ids = TextSegmentPageLocation.objects.values_list('page_revision_id', flat=True)
    page_revision_ids_to_check = child_page_revision_ids.intersection(submitted_page_revision_ids)

    for page_revision_id in page_revision_ids_to_check:
        total_segments, translated_segments = get_translation_progress(page_revision_id, tgt_locale)

        if total_segments == translated_segments:
            # Page revision is now complete
            handle_completed_revision(page_revision_id, src_locale, tgt_locale)


@receiver(post_save, sender=TextSegment)
def on_new_segment_translation(sender, instance, created, **kwargs):
    if created and instance.translation_of_id is not None:
        text_segment_page_locations = TextSegmentPageLocation.objects.filter(text_segment_id=instance.translation_of_id)
        html_segment_page_locations = HTMLSegmentPageLocation.objects.filter(html_segment__text_segments__text_segment_id=instance.translation_of_id)

        revision_ids = text_segment_page_locations.values_list('page_revision_id', flat=True).union(html_segment_page_locations.values_list('page_revision_id', flat=True))

        # Check if any translated pages can now be created
        for page_revision_id in revision_ids:
            total_segments, translated_segments = get_translation_progress(page_revision_id, instance.locale)

            if total_segments == translated_segments:
                # FIXME
                src_locale = Locale.default()

                # Page revision is now complete
                handle_completed_revision(page_revision_id, src_locale, instance.locale)


@transaction.atomic
def ingest_translations(src_locale, tgt_locale, translations):
    for source, translation in translations:
        src_text_segment = TextSegment.from_text(src_locale, source)
        TextSegment.from_text(tgt_locale, translation, translation_of=src_text_segment)
