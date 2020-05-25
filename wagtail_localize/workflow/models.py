from django.conf import settings
from django.db import models, transaction
from django.db.models import Case, Exists, OuterRef, When

from wagtail.core.models import Page, PageRevision
from wagtail_localize.models import Locale, TranslatableMixin
from wagtail_localize.translation.models import TranslatableRevision


class TranslationRequest(models.Model):
    source_locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, related_name="+"
    )
    target_locale = models.ForeignKey(
        Locale, on_delete=models.PROTECT, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
        related_name="wagtaillocalize_translation_requests_created",
    )

    sources = models.ManyToManyField(TranslationSource)

    @classmethod
    @transaction.atomic
    def from_instances(cls, instances, source_locale, target_locale, user=None):
        sources = []

        for instance in instances:
            if not isinstance(instance, TranslatableMixin):
                raise TypeError("Instance not translatable: %r" % instance)

            if instance.locale != source_locale:
                raise TypeError("Instance source locale mismatch: %r (%s != %s)" % (instance, instance.locale, source_locale))

            source, created = TranslationSource.from_instance(instance)
            sources.append(source)

        translation_request = cls.objects.create(
            source_locale=source_locale,
            target_locale=target_locale,
        )
        translation_request.sources.set(sources)

        # Recursively add all unmet dependencies to the request
        external_dependencies = translation_request.get_external_dependencies()
        handled_dependencies = set()
        while external_dependencies:
            for dep in external_dependencies:
                if dep.translation_key in handled_dependencies or dep.has_translation(target_locale):
                    handled_dependencies.add(dep.translation_key)
                    continue

                instance = dep.get_instance(source_locale)
                rev, created = TranslationSource.from_instance(instance)
                rev.extract_segments()
                translation_request.sources.add(rev)

                handled_dependencies.add(dep.translation_key)

            external_dependencies = translation_request.get_external_dependencies().exclude(translation_key__in=handled_dependencies)

        return translation_request

    def get_external_dependencies(self):
        """
        Returns queryset of TranslatableObjects that this request depends on that aren't handled by this request.
        """
        source_ids = self.sources.values_list('id', flat=True)
        return TranslatableObject.objects.filter(references__source_id__in=source_ids).exclude(sources__id__in=source_ids)
