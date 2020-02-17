from django.conf import settings
from django.db import models
from django.db.models import Case, Exists, OuterRef, When

from wagtail.core.models import Page, PageRevision
from wagtail_localize.models import Locale


class TranslationRequestQuerySet(models.QuerySet):
    def annotate_completed(self):
        """
        Adds an is_completed flag to each translation request. Which is true if at least
        one page is completed and no pages are in progress
        """
        in_progress_pages = TranslationRequestPage.objects.filter(
            request=OuterRef("pk")
        ).in_progress()
        completed_pages = TranslationRequestPage.objects.filter(
            request=OuterRef("pk")
        ).completed()

        return self.annotate(
            has_in_progress_pages=Exists(in_progress_pages),
            has_completed_pages=Exists(completed_pages),
            is_completed=Case(
                When(has_in_progress_pages=False, has_completed_pages=True, then=True),
                default=False,
                output_field=models.BooleanField(),
            ),
        )

    def completed(self):
        """
        Filters the queryset to contain only translation requests that have been translated.

        In order for this to be true, at least one of the translation pages must be translated
        and all others must not be in progress.
        """
        return self.annotate_completed().filter(is_completed=True)


class TranslationRequest(models.Model):
    # Protected foreign keys because locales shouldn't be deleted without manually dealing
    # with translation requests first
    source_locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, related_name="+"
    )
    target_locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, related_name="+"
    )

    # A foreign key to the page in destination tree where the translated pages will be created
    # If this is deleted before this translation request is complete, any remaining translations will be cancelled
    target_root = models.ForeignKey(
        Page, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    created_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="translation_requests_created",
    )

    objects = TranslationRequestQuerySet.as_manager()

    @property
    def is_cancelled(self):
        return self.target_root_id is None

    def get_status(self):
        # Are there any pages awaiting translation?
        if self.pages.in_progress().exists():
            if self.target_root_id is None:
                return "Cancelled (target page deleted)"
            else:
                return "In progress"

        else:
            # Has at least one page been translated successfully?
            if self.pages.completed().exists():
                return "Completed"
            else:
                return "Cancelled (all source pages deleted)"


class TranslationRequestPageQuerySet(models.QuerySet):
    def completed(self):
        """
        Filters the queryset to contain only translation request pages that have been successfully translated.
        """
        return self.filter(is_completed=True)

    def cancelled(self):
        """
        Filters the queryset to only include translation request pages which have been cancelled.

        Translation request pages will be automatically cancelled if their source page is deleted before
        the translation was complete.

        Note: this does not take into account the cancellation status of the translation request as a whole.
        """
        return self.filter(is_completed=False, source_revision__isnull=True)

    def in_progress(self):
        """
        Filters the queryset to include translation request pages that are awaiting translations.

        These include all incomplete translations that haven't been cancelled.

        Note: this does not take into account the cancellation status of the translation request as a whole.
        """
        return self.filter(is_completed=False, source_revision__isnull=False)


class TranslationRequestPage(models.Model):
    request = models.ForeignKey(
        TranslationRequest, on_delete=models.CASCADE, related_name="pages"
    )

    # source_revision will only be null if the original page or revision has been deleted.
    # in this case, we will treat this translation request as "Cancelled"
    source_revision = models.ForeignKey(
        PageRevision, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    # When a whole tree is submitted for translation, this allows that tree to be represented in translation requests.
    # When the translated pages are created, this is used to structure those pages in the same way as the source tree.
    # If this is null, the translated page must be created directly under request.target_root. All transation request
    # must have at least one page that has parent=null.
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, related_name="child_pages"
    )

    is_completed = models.BooleanField(default=False)

    # The revision that was created when this change was made
    # This is nullable because pages can be deleted later on
    completed_revision = models.ForeignKey(
        PageRevision, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    objects = TranslationRequestPageQuerySet.as_manager()

    @property
    def is_cancelled(self):
        # TODO: If this page's parent was cancelled, this should probably be marked as cancelled as well.
        return self.source_revision_id is None and not self.is_completed

    @property
    def source_page(self):
        return self.source_revision.page

    @property
    def previous_request(self):
        return (
            TranslationRequestPage.objects.filter(
                source_revision__page=self.source_page,
                request__target_locale=self.request.target_locale,
                id__lt=self.id,
            )
            .order_by("-request__created_at")
            .first()
        )

    def get_translation(self):
        return self.source_page.specific.get_translation(self.request.target_locale)
