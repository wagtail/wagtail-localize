from django.core.management.base import BaseCommand, CommandError

from wagtail.core.models import Page
from wagtail_localize.models import TranslatablePageMixin, Locale

from ...models import submit_to_pontoon, PontoonResourceSubmission


class Command(BaseCommand):
    def handle(self, **options):
        source_locale_id = Locale.objects.default_id()

        for page in Page.objects.live().specific().iterator():
            if not isinstance(page, TranslatablePageMixin):
                continue

            if page.locale_id != source_locale_id:
                continue

            if page.live_revision is not None:
                print(
                    f"Warning: The page '{page.title}' does not have a live_revision. Using latest revision instead."
                )
                page_revision = page.live_revision
            else:
                page_revision = page.get_latest_revision() or page.save_revision(
                    changed=False
                )

            print(f"Submitting '{page.title}'")

            if PontoonResourceSubmission.objects.filter(
                page_revision=page_revision
            ).exists():
                print("Already submitted!")
                continue

            submit_to_pontoon(page, page_revision)
