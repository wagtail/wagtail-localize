import logging
from django.db import models
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from wagtail.models import Page, Locale
from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.operations import translate_object
from wagtail_localize.views import edit_translation
from wagtail_localize.machine_translators import get_machine_translator
from typing import List, Type, Optional

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "language_code",
            type=str,
            help="Source language code to copy pages from")
        parser.add_argument(
            "--exclude",
            nargs="*",
            type=str,
            help="List of model names to exclude from translation")
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Run without making any actual changes")

    def get_exclude_models(self, model_names: List[str]) -> List[Type[models.Model]]:
        """ Convert model names to actual model classes."""
        exclude_models = []
        for model_name in model_names:
            found_model = None
            for model in apps.get_models():
                if model.__name__ == model_name:
                    found_model = model
                    break

            if found_model:
                exclude_models.append(found_model)
                self.stdout.write(f"Excluded model: {model_name}")
            else:
                self.stderr.write(f"Model '{model_name}' not found in any installed app.")
        return exclude_models

    def get_admin_user(self) -> Optional[User]:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stderr.write("Error: No superuser found in the system.")
            return None
        return admin_user

    def copy_pages(self, admin_user, pages_locale_language: models.QuerySet, exclude_models: List[Type[models.Model]], dry_run: bool):
        """Copy pages to all other locales."""
        locales = Locale.objects.all()

        for page in pages_locale_language:
            if page.is_root():
                continue

            if isinstance(page.specific, tuple(exclude_models)):
                logger.info(f"Skipped excluded model: {page.specific._meta.model_name} (ID: {page.id})")
                continue

            try:
                if not dry_run:
                    translate_object(page, locales)
                    (
                        TranslationSource.objects
                        .update_or_create_from_instance(page.specific)
                        .create_or_update_translation(
                            locale=page.locale,
                            user=admin_user,
                            publish=True
                        )
                    )
                self.stdout.write(f"Processed page: {page.title} (ID: {page.id})")
            except TypeError as e:
                logger.error(f"TypeError on page: {page.title} (ID: {page.id}): {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing page: {page.title} (ID: {page.id}): {e}")
                continue

    def translate_pages(self, pages_to_translate: models.QuerySet, excluded_models: List[Type[models.Model]],
                        admin_user: User, dry_run: bool):
        """Apply machine translation to copied pages."""
        machine_translator = get_machine_translator()

        for page in pages_to_translate:
            if isinstance(page.specific, tuple(excluded_models)):
                continue

            try:
                translation_source, created = TranslationSource.update_or_create_from_instance(page.specific)

                # Get translation
                translation = Translation.objects.get(
                    source__object_id=page.translation_key,
                    target_locale_id=page.locale_id,
                    enabled=True
                )

                if not dry_run:
                    try:
                        # Apply machine translation
                        if edit_translation.apply_machine_translation(
                            translation.id,
                            admin_user,
                            machine_translator
                        ):
                            self.stdout.write(
                                f"Successfully translated page {page.title} with {machine_translator.display_name}")

                            try:
                                # Create or update the translation
                                translation_source.create_or_update_translation(
                                    locale=page.locale,
                                    user=admin_user,
                                    publish=True
                                )

                                self.stdout.write(f"Successfully saved and published translation for {page.title}")

                            except ValidationError as ve:
                                self.stderr.write(f"Validation error while saving page {page.title}: {str(ve)}")
                            except Exception as e:
                                self.stderr.write(f"Error while saving page {page.title}: {str(e)}")
                        else:
                            self.stdout.write(f"No new translations needed for page {page.title}")

                    except Exception as e:
                        self.stderr.write(f"Error during translation process for page {page.title}: {str(e)}")
                else:
                    self.stdout.write(f"Would translate page: {page.title} (ID: {page.id})")

            except Translation.DoesNotExist:
                logger.warning(
                    f"Translation object does not exist or is not enabled for page {page.title} (ID: {page.id})")
            except Exception as e:
                logger.error(f"Error processing translation for page {page.title} (ID: {page.id}): {str(e)}")

        self.stdout.write("Completed translation process")

    def handle(self, *args, **options):
        try:
            Locale.objects.get(language_code=options['language_code'])
        except Locale.DoesNotExist:
            self.stderr.write(f"Error: Locale with language code {options['language_code']} not found")
            return

        exclude_models = self.get_exclude_models(options['exclude'] or [])

        admin_user = self.get_admin_user()
        if not admin_user:
            return

        pages_locale_language = Page.objects.filter(locale__language_code=options['language_code'])
        pages_to_translate = Page.objects.exclude(locale__language_code=options['language_code'])

        if options['dry_run']:
            self.stdout.write("Running in dry-run mode - no changes will be made")

        # Step 1: Copy pages to other locales
        self.stdout.write("Starting page copy process...")
        self.copy_pages(admin_user, pages_locale_language, exclude_models, options['dry_run'])

        # Step 2: Apply machine translation
        self.stdout.write("Starting translation process...")
        self.translate_pages(pages_to_translate, exclude_models, admin_user, options['dry_run'])

        self.stdout.write(self.style.SUCCESS("Translation process completed"))
