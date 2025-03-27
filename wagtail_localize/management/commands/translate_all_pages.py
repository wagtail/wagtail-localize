import logging
from typing import List, Type, Optional, Callable, TypeVar
from django.db import models
from django.apps import apps
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from wagtail.models import Page, Locale
from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.operations import translate_object
from wagtail_localize.views import edit_translation
from wagtail_localize.machine_translators import get_machine_translator

logger = logging.getLogger(__name__)
User = get_user_model()
T = TypeVar('T', bound=models.Model)


class Command(BaseCommand):
    def add_arguments(self, parser) -> None:
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

    def _get_exclude_models(self, model_names: List[str]) -> List[Type[models.Model]]:
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

    def _get_admin_user(self) -> Optional[User]:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stderr.write("Error: No superuser found in the system.")
        return admin_user

    def _handle_page_operation(self, page: Page, operation_func: Callable,
                               error_msg: str, dry_run: bool) -> bool:
        if dry_run:
            self.stdout.write(f"Would process page: {page.title} (ID: {page.id})")
            return True

        try:
            operation_func()
            self.stdout.write(f"Processed page: {page.title} (ID: {page.id})")
            return True
        except Exception as e:
            logger.error(f"{error_msg}: {page.title} (ID: {page.id}): {e}")
            return False

    def _should_process_page(self, page: Page, exclude_models: List[Type[models.Model]]) -> bool:
        return not (page.is_root() or isinstance(page.specific, tuple(exclude_models)))

    def _copy_page(self, page: Page, admin_user: User, locales: models.QuerySet) -> bool:
        translate_object(page, locales)
        translation_source, created = TranslationSource.get_or_create_from_instance(page.specific)
        translation_source.create_or_update_translation(
            locale=page.locale,
            user=admin_user,
            publish=True,
            fallback=True
        )
        translation_source.update_from_db()
        return True

    def copy_pages(self, admin_user: User, pages_locale_language: models.QuerySet,
                   exclude_models: List[Type[models.Model]], dry_run: bool) -> None:
        locales = Locale.objects.all()

        for page in pages_locale_language:
            if not self._should_process_page(page, exclude_models):
                continue

            self._handle_page_operation(
                page,
                lambda: self._copy_page(page, admin_user, locales),
                "Error processing page",
                dry_run
            )

    def _translate_page(self, page: Page, admin_user: User) -> bool:
        machine_translator = get_machine_translator()
        translation_source, _ = TranslationSource.update_or_create_from_instance(page.specific)

        translation = Translation.objects.filter(
            source__object_id=page.translation_key,
            target_locale_id=page.locale_id,
            enabled=True
        ).first()

        if not translation:
            return False

        if edit_translation.apply_machine_translation(
            translation.id,
            admin_user,
            machine_translator
        ):
            translation_source.create_or_update_translation(
                locale=page.locale,
                user=admin_user,
                publish=True,
                fallback=True
            )
            return True
        return False

    def translate_pages(self, pages_to_translate: models.QuerySet,
                        excluded_models: List[Type[models.Model]],
                        admin_user: User, dry_run: bool) -> None:
        for page in pages_to_translate:
            if not self._should_process_page(page, excluded_models):
                continue

            self._handle_page_operation(
                page,
                lambda: self._translate_page(page, admin_user),
                "Error processing translation",
                dry_run
            )

    def handle(self, *args, **options) -> None:
        try:
            Locale.objects.get(language_code=options['language_code'])
        except Locale.DoesNotExist:
            self.stderr.write(f"Error: Locale with language code {options['language_code']} not found")
            return

        admin_user = self._get_admin_user()
        if not admin_user:
            return

        exclude_models = self._get_exclude_models(options['exclude'] or [])
        pages_locale_language = Page.objects.filter(locale__language_code=options['language_code'])

        if options['dry_run']:
            self.stdout.write("Running in dry-run mode - no changes will be made")

        self.stdout.write("Starting page copy process...")
        self.copy_pages(admin_user, pages_locale_language, exclude_models, options['dry_run'])

        pages_to_translate = Page.objects.exclude(locale__language_code=options['language_code'])
        self.stdout.write("Starting translation process...")
        self.translate_pages(pages_to_translate, exclude_models, admin_user, options['dry_run'])

        self.stdout.write(self.style.SUCCESS("Translation process completed"))
