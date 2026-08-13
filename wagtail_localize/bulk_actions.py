from django.utils.translation import gettext_lazy as _
from wagtail.admin.views.pages.bulk_actions.page_bulk_action import PageBulkAction

from wagtail_localize.models import TranslationSource
from wagtail_localize.views.update_translations import sync_translation_source


class PublishAndSyncTranslationsBulkAction(PageBulkAction):
    display_name = _("Publish & sync translations")
    action_type = "publish-and-sync-translations"
    aria_label = _("Publish selected pages and sync translations")
    template_name = (
        "wagtail_localize/admin/pages/bulk_actions/confirm_publish_and_sync.html"
    )
    action_priority = 45

    def check_perm(self, page):
        return page.permissions_for_user(self.request.user).can_publish()

    @classmethod
    def execute_action(cls, objects, include_descendants=False, user=None, **kwargs):
        num_parent_objects = 0
        num_child_objects = 0

        def publish_page(page):
            specific_page = page.specific
            revision = page.get_latest_revision()
            if revision is None:
                revision = specific_page.save_revision(user=user)
            revision.publish(user=user)

            source = TranslationSource.objects.get_for_instance_or_none(specific_page)
            if source is not None:
                sync_translation_source(source, user=user, publish=True)

        for page in objects:
            publish_page(page)
            num_parent_objects += 1

            if include_descendants:
                descendants = (
                    page.get_descendants()
                    .not_live()
                    .defer_streamfields()
                    .specific()
                    .iterator()
                )
                for descendant in descendants:
                    if (
                        user is None
                        or descendant.permissions_for_user(user).can_publish()
                    ):
                        publish_page(descendant)
                        num_child_objects += 1

        return num_parent_objects, num_child_objects
