from django.conf import settings
from django.db import models

from wagtail.core.models import Page, PageRevision
from wagtail_i18n.models import Locale


class TranslationRequest(models.Model):
    source_locale = models.ForeignKey(Locale, on_delete=models.CASCADE, related_name='+')
    target_locale = models.ForeignKey(Locale, on_delete=models.CASCADE, related_name='+')
    target_root = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='translation_requests_created')

    def get_status(self):
        num_total = self.pages.count()
        num_completed = self.pages.filter(is_completed=True).count()

        if num_total == num_completed:
            return "Completed"
        else:
            return "In progress"


class TranslationRequestPage(models.Model):
    request = models.ForeignKey(TranslationRequest, on_delete=models.CASCADE, related_name='pages')
    # FIXME: what if the original page is deleted?
    source_revision = models.ForeignKey(PageRevision, on_delete=models.CASCADE, related_name='+')
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, related_name='child_pages')
    is_completed = models.BooleanField(default=False)

    # The revision that was created when this change was made
    # Nullable as pages can be deleted later on
    completed_revision = models.ForeignKey(PageRevision, on_delete=models.SET_NULL, null=True, related_name='+')

    @property
    def source_page(self):
        return self.source_revision.page

    @property
    def previous_request(self):
        return TranslationRequestPage.objects.filter(source_revision__page=self.source_page, request__target_locale=self.request.target_locale, id__lt=self.id).order_by('-request__created_at').first()

    def get_translation(self):
        return self.source_page.specific.get_translation(self.request.target_locale)
