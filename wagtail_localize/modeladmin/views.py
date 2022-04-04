from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin import messages
from wagtail.contrib.modeladmin.views import (
    ChooseParentView,
    CreateView,
    DeleteView,
    EditView,
    IndexView,
    InspectView,
)
from wagtail.core.models import Locale, TranslatableMixin
from wagtail.utils.version import get_main_version

from wagtail_localize.models import Translation
from wagtail_localize.views import edit_translation


if WAGTAIL_VERSION >= (2, 15):
    from wagtail.contrib.modeladmin.views import HistoryView
else:
    HistoryView = object


class TranslatableViewMixin:
    def __init__(self, *args, **kwargs):
        self.locale = None
        super().__init__(*args, **kwargs)

        if not issubclass(self.model, TranslatableMixin):
            raise ImproperlyConfigured(
                f"Model `{self.model}` used in translatable view `{self.__class__}` "
                f"must subclass the `{TranslatableMixin}` class."
            )

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if getattr(self, "instance", None):
            self.locale = self.instance.locale
        if "locale" in request.GET:
            self.locale = get_object_or_404(Locale, language_code=request.GET["locale"])
        if not self.locale:
            self.locale = Locale.get_active()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["locale"] = self.locale
        context["translations"] = []
        context["wagtail_version"] = get_main_version()
        return context


class TranslatableIndexView(TranslatableViewMixin, IndexView):
    def get_filters(self, request):
        filters = super().get_filters(request)
        filters[2]["locale"] = self.locale.id
        return filters

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = [
            {
                "locale": locale,
                "url": self.index_url + "?locale=" + locale.language_code,
            }
            for locale in Locale.objects.exclude(id=self.locale.id)
        ]
        return context


class TranslatableCreateView(TranslatableViewMixin, CreateView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"].locale = self.locale
        return kwargs

    def get_success_url(self):
        return self.index_url + "?locale=" + self.locale.language_code

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = [
            {
                "locale": locale,
                "url": self.create_url + "?locale=" + locale.language_code,
            }
            for locale in Locale.objects.exclude(id=self.locale.id)
        ]
        return context


class TranslatableEditView(TranslatableViewMixin, EditView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.translation = Translation.objects.filter(
            source__object_id=self.instance.translation_key,
            target_locale_id=self.instance.locale_id,
        ).first()

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        # Check if the user has clicked the "Start Synced translation" menu item
        if (
            request.method == "POST"
            and "localize-restart-translation" in request.POST
            and self.translation
            and not self.translation.enabled
        ):
            return edit_translation.restart_translation(
                request, self.translation, self.instance
            )

        # Overrides the edit view if the object is translatable and the target of a translation
        if self.translation and self.translation.enabled:
            return edit_translation.edit_translation(
                request, self.translation, self.instance
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translation"] = self.translation
        context["translations"] = [
            {
                "locale": translation.locale,
                "url": self.url_helper.get_action_url("edit", translation.pk)
                + "?locale="
                + translation.locale.language_code,
            }
            for translation in self.instance.get_translations().select_related("locale")
        ]
        return context


class TranslatableInspectView(TranslatableViewMixin, InspectView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = [
            {
                "locale": translation.locale,
                "url": self.url_helper.get_action_url("inspect", translation.pk)
                + "?locale="
                + translation.locale.language_code,
            }
            for translation in self.instance.get_translations().select_related("locale")
        ]
        return context


class TranslatableDeleteView(TranslatableViewMixin, DeleteView):
    pass


class TranslatableHistoryView(TranslatableViewMixin, HistoryView):
    pass


class TranslatableChooseParentView(TranslatableViewMixin, ChooseParentView):
    pass
