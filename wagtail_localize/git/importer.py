from django.core.exceptions import ValidationError
from django.db import transaction

from wagtail_localize.models import MissingRelatedObjectError, StringNotUsedInContext, UnknownContext, UnknownString

from .models import SyncLog


class Importer:
    def __init__(self, commit_id, logger):
        self.logger = logger
        self.log = SyncLog.objects.create(
            action=SyncLog.ACTION_PULL, commit_id=commit_id
        )

    @transaction.atomic
    def import_resource(self, translation, po):
        for warning in translation.import_po(po, tool_name="Pontoon"):
            if isinstance(warning, UnknownContext):
                self.logger.warning(f"While translating '{translation.source.object_repr}' into {translation.target_locale.get_display_name()}: Unrecognised context '{warning.context}'")

            elif isinstance(warning, UnknownString):
                self.logger.warning(f"While translating '{translation.source.object_repr}' into {translation.target_locale.get_display_name()}: Unrecognised string '{warning.string}'")

            elif isinstance(warning, StringNotUsedInContext):
                self.logger.warning(f"While translating '{translation.source.object_repr}' into {translation.target_locale.get_display_name()}: The string '{warning.string}' is not used in context  '{warning.context}'")

        try:
            translation.save_target()

        except MissingRelatedObjectError:
            # Ignore error if there was a missing related object
            # In this case, the translations will just be updated but the page
            # wont be updated. When the related object is translated, the user
            # can manually hit the save draft/publish button to create/update
            # this page.
            self.logger.warning(f"Unable to translate '{translation.source.object_repr}' into {translation.target_locale.get_display_name()}: Missing related object")

        except ValidationError as e:
            # Also ignore any validation errors
            self.logger.warning(f"Unable to translate '{translation.source.object_repr}' into {translation.target_locale.get_display_name()}: {repr(e)}")

        self.log.add_translation(translation)
