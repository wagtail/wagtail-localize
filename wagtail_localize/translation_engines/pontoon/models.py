from pathlib import PurePosixPath

from django.conf import settings
from django.db import models, transaction
from django.db.models import Exists, OuterRef
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from wagtail.core.signals import page_published
from wagtail_localize.models import TranslatablePageMixin, Locale, Language
from wagtail_localize.segments import RelatedObjectValue
from wagtail_localize.segments.extract import extract_segments
from wagtail_localize.translation_memory.models import (
    Segment,
    SegmentLocation,
    TranslatableObject,
    TranslatableRevision,
    RelatedObjectLocation,
    SegmentTranslation,
)
from wagtail_localize.translation_memory.utils import (
    insert_segments,
    get_translation_progress,
)


class PontoonSyncLog(models.Model):
    ACTION_PUSH = 1
    ACTION_PULL = 2

    ACTION_CHOICES = [(ACTION_PUSH, "Push"), (ACTION_PULL, "Pull")]

    action = models.PositiveIntegerField(choices=ACTION_CHOICES)
    time = models.DateTimeField(auto_now_add=True)
    commit_id = models.CharField(max_length=40, blank=True)


class PontoonResource(models.Model):
    object = models.OneToOneField(
        "wagtail_localize_translation_memory.TranslatableObject",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="+",
    )

    # The path within the locale folder in the git repository to push the PO file to
    # This is initially the pages URL path but is not updated if the page is moved
    path = models.CharField(max_length=255, unique=True)

    # The last revision to be submitted for translation
    # This is denormalised from the revision field of the latest submission for this resource
    current_revision = models.OneToOneField(
        "wagtail_localize_translation_memory.TranslatableRevision",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )

    @classmethod
    def get_unique_path_from_urlpath(cls, url_path):
        """
        Returns a unique path derived from the given url path taken from a Page object.

        We never change paths, even if a page has been moved in order to not confuse Pontoon.

        But this means that if pages are moved and a new one is created with the same slug in
        it's previous position, a path name clash could occur.
        """
        path = url_path.strip("/")

        # We're not using the 'fast' technique Wagtail uses to find unique slugs here. This is because
        # a prefix query on path could potentially lead to a massive amount of results being returned.
        path_suffix = 1
        try_path = path
        while cls.objects.filter(path=try_path).exists():
            try_path = f"{path}-{path_suffix}"
            path_suffix += 1

            if path_suffix > 100:
                # Unlikely to get here, but I feel uncomfortable about leaving this loop unrestrained!
                raise Exception(f"Unable to find a unique path for: {url_path}")

        return try_path

    def get_po_filename(self, language=None):
        """
        Returns the filename of this resource within the git repository that is shared with Pontoon.

        If a language is specified, the filename for that language is returned. Otherwise, the filename
        of the template is returned.
        """
        if language is not None:
            base_path = PurePosixPath(f"locales/{language.as_rfc5646_language_tag()}")
        else:
            base_path = PurePosixPath("templates")

        return (base_path / self.path).with_suffix(
            ".pot" if language is None else ".po"
        )

    def get_locale_po_filename_template(self):
        """
        Returns the template used for language-specific files for this resource.

        This value is passed to Pontoon in the configuration so it can find the language-specific files.
        """
        return (PurePosixPath("locales/{locale}") / self.path).with_suffix(".po")

    @classmethod
    def get_by_po_filename(cls, filename):
        """
        Finds the resource/language for the given filename of a PO file in the git repo.

        May raise PontoonResource.DoesNotExist or Language.DoesNotExist.
        """
        parts = PurePosixPath(filename).parts
        if parts[0] == "templates":
            path = PurePosixPath(*parts[1:]).with_suffix("")
            return cls.objects.get(path=path), None
        elif parts[0] == "locales":
            path = PurePosixPath(*parts[2:]).with_suffix("")
            return (
                cls.objects.get(path=path),
                # NOTE: Pontoon Uses RFC 5646 style language tags
                # but since this is a site that relies on Pontoon
                # for translation, we assumme that Language model
                # uses RFC 5646 style language tags as well.
                # If this isn't the case, then the following
                # commented-out line should be used instead.
                #
                # TODO: Think of a way to make this configurable.
                #
                # Language.get_by_rfc5646_language_tag(parts[1]),
                Language.objects.get(code=parts[1]),
            )

        raise cls.DoesNotExist(
            "Filename must begin with either 'templates' or 'locales'"
        )

    def get_segments(self):
        """
        Gets all segments that are in the latest submission to Pontoon.
        """
        return SegmentLocation.objects.filter(revision_id=self.current_revision_id)

    def get_obsolete_translations(self, language):
        """
        Gets all past translations for this resource that are not used in
        the latest submission.
        """
        return SegmentTranslation.objects.annotate(
            is_in_latest_submission=Exists(
                SegmentLocation.objects.filter(
                    revision_id=self.current_revision_id,
                    segment_id=OuterRef("translation_of_id"),
                    context_id=OuterRef("context_id"),
                )
            )
        ).filter(language=language, is_in_latest_submission=False,)

    def find_translatable_submission(self, language):
        """
        Look to see if a submission is ready for translating.

        The returned submission will be the latest submission that is ready for translation, after any previous
        translated submission.

        A submission is considered translatable if all the strings in the submission have been translated into the
        target language and the translated page hasn't been updated for a later submission.
        """
        submissions_to_check = self.submissions.order_by("-created_at")

        # Exclude submissions that pre-date the last translated submission
        last_translated_submission = (
            self.submissions.annotate_translated(language)
            .filter(is_translated=True)
            .order_by("created_at")
            .last()
        )
        if last_translated_submission is not None:
            submissions_to_check = submissions_to_check.filter(
                created_at__gte=last_translated_submission.created_at
            )

        for submission in submissions_to_check:
            total_segments, translated_segments = submission.get_translation_progress(
                language
            )

            if translated_segments == total_segments:
                return submission

    def latest_submission(self):
        return self.submissions.latest("created_at")

    def latest_pushed_submission(self):
        return self.submissions.filter(pushed_at__isnull=False).latest("created_at")

    def get_dependees(self):
        """
        Gets a QuerySet of PontoonResourceSubmissions that depend on this Resource.

        This is where this resource reprensents a reusable snippet or images that
        other resources link to and can't be translated until this resource is
        translated.

        This is the opposite of PontoonResourceSubmission.get_dependencies
        """
        return PontoonResourceSubmission.objects.filter(
            revision_id__in=self.object.references.values_list("revision_id", flat=True)
        )

    def __repr__(self):
        return f"<PontoonResource '{self.get_po_filename()}'>"


class PontoonSyncLogResourceQuerySet(models.QuerySet):
    def unique_resources(self):
        return PontoonResource.objects.filter(
            page_id__in=self.values_list("resource_id", flat=True)
        )

    def unique_languages(self):
        return Language.objects.filter(
            id__in=self.values_list("language_id", flat=True)
        )


class PontoonSyncLogResource(models.Model):
    log = models.ForeignKey(
        PontoonSyncLog, on_delete=models.CASCADE, related_name="resources"
    )
    resource = models.ForeignKey(
        PontoonResource, on_delete=models.CASCADE, related_name="logs"
    )

    # Null if pushing this resource, otherwise set to the language being pulled
    language = models.ForeignKey(
        "wagtail_localize.Language",
        null=True,
        on_delete=models.CASCADE,
        related_name="+",
    )

    objects = PontoonSyncLogResourceQuerySet.as_manager()


class PontoonResourceSubmissionQuerySet(models.QuerySet):
    def annotate_translated(self, language):
        """
        Adds is_translated flag which is True if the submission has been translated into the specified language.
        """
        return self.annotate(
            is_translated=Exists(
                PontoonResourceTranslation.objects.filter(
                    submission_id=OuterRef("pk"), language=language
                )
            )
        )


class PontoonResourceSubmission(models.Model):
    resource = models.ForeignKey(
        PontoonResource, on_delete=models.CASCADE, related_name="submissions"
    )

    revision = models.OneToOneField(
        "wagtail_localize_translation_memory.TranslatableRevision",
        on_delete=models.CASCADE,
        related_name="pontoon_submission",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')

    pushed_at = models.DateTimeField(null=True)
    push_log = models.ForeignKey(
        PontoonSyncLog,
        null=True,
        on_delete=models.SET_NULL,
        related_name="pushed_submissions",
    )

    objects = PontoonResourceSubmissionQuerySet.as_manager()

    def get_translation_progress(self, language):
        """
        Get the current translation progress into the specified language.

        Returns two integers:
        - The total number of segments in the submission to translate
        - The number of segments that have been translated into the target language
        """
        return get_translation_progress(self.revision_id, language)

    def get_dependencies(self):
        """
        Gets a QuerySet of resources that this submission depends on.

        These are any linked objects (eg, snippets, images) that must
        be translated before this resource can be translated.

        This is the opposite of PontoonResource.get_dependees
        """
        return PontoonResource.objects.filter(
            object_id__in=RelatedObjectLocation.objects.filter(
                revision_id=self.revision_id
            ).values_list("object_id", flat=True)
        )


class PontoonResourceTranslation(models.Model):
    """
    Represents a translation that was sucessfully carried out by pontoon.
    """

    submission = models.ForeignKey(
        PontoonResourceSubmission, on_delete=models.CASCADE, related_name="translations"
    )
    language = models.ForeignKey(
        "wagtail_localize.Language",
        on_delete=models.CASCADE,
        related_name="pontoon_translations",
    )

    created_at = models.DateTimeField(auto_now_add=True)


@transaction.atomic
def submit_to_pontoon(instance):
    revision, created = TranslatableRevision.from_instance(instance)

    if not created:
        # Check if there is already a submission for this revision
        if PontoonResourceSubmission.objects.filter(revision=revision).exists():
            return

    # Extract segments from revision and save them to translation memory
    segments = extract_segments(instance)
    insert_segments(revision, revision.locale.language_id, segments)

    # Recurse into any related objects
    for segment in segments:
        if not isinstance(segment, RelatedObjectValue):
            continue

        submit_to_pontoon(segment.get_instance(revision.locale))

    base_model = instance.get_translation_model()

    resource, created = PontoonResource.objects.get_or_create(
        object=revision.object,
        defaults={
            "path": PontoonResource.get_unique_path_from_urlpath(
                f"{slugify(base_model._meta.verbose_name_plural)}/{instance.pk}"
            ),
        },
    )

    resource.current_revision = revision
    resource.save(update_fields=["current_revision"])

    # Create submission
    resource.submissions.create(revision=revision)


@transaction.atomic
def submit_page_to_pontoon(page_revision):
    revision, created = TranslatableRevision.get_or_create_from_page_revision(
        page_revision
    )

    if not created:
        # Check if there is already a submission for this revision
        if PontoonResourceSubmission.objects.filter(revision=revision).exists():
            return

    # Extract segments from revision and save them into translation memory
    segments = extract_segments(page_revision.as_page_object())
    insert_segments(revision, revision.locale.language_id, segments)

    # Recurse into any related objects
    for segment in segments:
        if not isinstance(segment, RelatedObjectValue):
            continue

        submit_to_pontoon(segment.get_instance(revision.locale))

    resource, created = PontoonResource.objects.get_or_create(
        object=revision.object,
        defaults={
            "path": PontoonResource.get_unique_path_from_urlpath(
                "pages" + page_revision.page.url_path
            ),
        },
    )

    resource.current_revision = revision
    resource.save(update_fields=["current_revision"])

    # Create submission
    resource.submissions.create(revision=revision)


@receiver(page_published)
def submit_page_to_pontoon_on_publish(sender, **kwargs):
    if issubclass(sender, TranslatablePageMixin):
        page = kwargs["instance"]
        page_revision = kwargs["revision"]

        if page.locale_id == Locale.objects.default_id():
            submit_page_to_pontoon(page_revision)
