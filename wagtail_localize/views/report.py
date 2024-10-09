import django_filters

from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy
from django_filters.constants import EMPTY_VALUES
from django_filters.fields import ModelChoiceField
from modelcluster.fields import ParentalKey
from wagtail import VERSION as WAGTAIL_VERSION
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


def _adapt_wagtail_report_attributes(cls):
    """
    A class decorator that adapts ReportView-derived classes for compatibility
    with multiple versions of Wagtail by conditionally assigning attributes
    based on the Wagtail version. This includes setting appropriate titles,
    and adjusting template names and URL names for AJAX support since Wagtail 6.2.

    Attributes adjusted:
    - `title` or `page_title` based on Wagtail version for the display name of the report.
    - For Wagtail 6.2 and above, additional attributes like `results_template_name`,
      `index_results_url_name`, and `index_url_name` are set to support AJAX updates
      and utilize the `wagtail.admin.ui.tables` framework.
    """
    if WAGTAIL_VERSION < (6, 2):
        cls.title = gettext_lazy("Translations")
    else:
        # The `title` attr was **changed** to `page_title` in Wagtail 6.2
        cls.page_title = gettext_lazy("Translations")
        # The `results_template_name` attr was **added** in Wagtail 6.2
        # to support updating the listing via AJAX upon filtering and
        # to allow the use of the `wagtail.admin.ui.tables` framework.
        cls.results_template_name = (
            "wagtail_localize/admin/translations_report_results.html"
        )
        # The `index_results_url_name` attr was **added** in Wagtail 6.2
        # to support updating the listing via AJAX upon filtering.
        cls.index_results_url_name = "wagtail_localize:translations_report_results"
        cls.index_url_name = "wagtail_localize:translations_report"
    return cls


@_adapt_wagtail_report_attributes
class TranslationsReportView(ReportView):
    template_name = "wagtail_localize/admin/translations_report.html"
    header_icon = "site"

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
