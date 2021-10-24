import django_filters

from django.contrib.contenttypes.models import ContentType
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy
from django_filters.constants import EMPTY_VALUES
from django_filters.fields import ModelChoiceField
from modelcluster.fields import ParentalKey
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.views.reports import ReportView
from wagtail.core.models import get_translatable_models

from wagtail_localize.models import Translation


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


class LocaleFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        return qs.filter(**{self.field_name + "__language_code": value})


class TranslationsReportFilterSet(WagtailFilterSet):
    content_type = ContentTypeModelChoiceFilter(
        field_name="source__specific_content_type", label=gettext_lazy("Content type")
    )
    source_title = SourceTitleFilter(label=gettext_lazy("Source title"))
    source_locale = LocaleFilter(field_name="source__locale")
    target_locale = LocaleFilter()

    class Meta:
        model = Translation
        fields = ["content_type", "source_title", "source_locale", "target_locale"]


class TranslationsReportView(ReportView):
    template_name = "wagtail_localize/admin/translations_report.html"
    title = gettext_lazy("Translations")
    header_icon = "site"

    filterset_class = TranslationsReportFilterSet

    def get_queryset(self):
        return Translation.objects.all()
