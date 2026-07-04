import django_filters

from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy
from django_filters.constants import EMPTY_VALUES
from django_filters.fields import ModelChoiceField
from modelcluster.fields import ParentalKey
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.views.reports import ReportView
from wagtail.coreutils import get_content_languages
from wagtail.models import get_translatable_models

from wagtail_localize.models import StringSegment, StringTranslation, Translation


class SourceTitleFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        return qs.filter(source__object_repr__icontains=value)


class ContentTypeModelChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return capfirst(obj.name)


class ContentTypeModelChoiceFilter(django_filters.ModelChoiceFilter):
    field_class = ContentTypeModelChoiceField

    def get_translatable_models(self, descendant_of=None):
        """
        Returns a list of model classes that are usable in this filter.

        When descendant_of is set, the models will be filtered to only include those that inherit from this model
        (includes the model itself if it's translatable)
        """
        translatable_models = get_translatable_models(include_subclasses=True)

        # Remove child models
        translatable_models = [
            model
            for model in translatable_models
            if not any(
                isinstance(field, ParentalKey) for field in model._meta.get_fields()
            )
        ]

        # Filter content types to only include those based on the provided type
        if descendant_of is not None:
            translatable_models = [
                model
                for model in translatable_models
                if issubclass(model, descendant_of)
            ]

        return translatable_models

    def get_queryset(self, request):
        """
        Returns QuerySet of ContentTypes to show in the filter.

        Called from django_filters.
        """
        translatable_models = self.get_translatable_models()

        # Return QuerySet of content types
        return ContentType.objects.filter(
            id__in=[
                content_type.id
                for content_type in ContentType.objects.get_for_models(
                    *translatable_models
                ).values()
            ]
        ).order_by("model")

    def filter(self, qs, value):
        """
        Filters the QuerySet to only include translations for the select content type and any descendant content types

        Called from django_filters.
        """
        if value in EMPTY_VALUES:
            return qs

        # Filter by content types that inherit from this one as well
        translatable_models = self.get_translatable_models(
            descendant_of=value.model_class()
        )
        return qs.filter(
            source__specific_content_type_id__in=[
                content_type.id
                for content_type in ContentType.objects.get_for_models(
                    *translatable_models
                ).values()
            ]
        )


def _get_locale_choices():
    return list(get_content_languages().items())


class LocaleFilter(django_filters.ChoiceFilter):
    def filter(self, qs, value):
        if not value or value == self.null_value:
            return qs

        return qs.filter(**{self.field_name + "__language_code": value})


class TranslationsReportFilterSet(WagtailFilterSet):
    content_type = ContentTypeModelChoiceFilter(
        field_name="source__specific_content_type", label=gettext_lazy("Content type")
    )
    source_title = SourceTitleFilter(label=gettext_lazy("Source title"))
    source_locale = LocaleFilter(
        field_name="source__locale",
        choices=_get_locale_choices,
        empty_label=None,
        null_label=gettext_lazy("All"),
        null_value="all",
    )
    target_locale = LocaleFilter(
        choices=_get_locale_choices,
        empty_label=None,
        null_label=gettext_lazy("All"),
        null_value="all",
    )
    waiting_for_translation = django_filters.BooleanFilter(
        label=gettext_lazy("Waiting for translations"),
    )

    class Meta:
        model = Translation
        fields = [
            "content_type",
            "source_title",
            "source_locale",
            "target_locale",
            "waiting_for_translation",
        ]


class TranslationsReportView(ReportView):
    template_name = "wagtail_localize/admin/translations_report.html"
    results_template_name = "wagtail_localize/admin/translations_report_results.html"
    index_url_name = "wagtail_localize:translations_report"
    index_results_url_name = "wagtail_localize:translations_report_results"
    header_icon = "site"
    page_title = gettext_lazy("Translations")

    filterset_class = TranslationsReportFilterSet

    def get_queryset(self):
        return Translation.objects.annotate(
            # Check to see if there is at least one string segment that is not
            # translated.
            waiting_for_translation=Exists(
                StringSegment.objects.filter(source_id=OuterRef("source_id"))
                .annotate(
                    # Annotate here just to filter in the next subquery, as Django
                    # doesn't have support for nested OuterRefs.
                    _target_locale_id=OuterRef("target_locale_id"),
                    is_translated=Exists(
                        StringTranslation.objects.filter(
                            translation_of_id=OuterRef("string_id"),
                            context_id=OuterRef("context_id"),
                            locale_id=OuterRef("_target_locale_id"),
                            has_error=False,
                        )
                    ),
                )
                .filter(is_translated=False)
            )
        )
