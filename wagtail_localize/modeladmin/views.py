from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
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
    from wagtail.core.log_actions import log
else:
    HistoryView = object

    def log(instance, action):
        pass


class TranslatableViewMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not issubclass(self.model, TranslatableMixin):
            raise ImproperlyConfigured(
                f"Model `{self.model}` used in translatable view `{self.__class__}` "
                f"must subclass the `{TranslatableMixin}` class."
            )

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        self.locale = self.get_locale(request)
        self.model_admin.locale = self.locale
        self.model_admin.url_helper.locale = self.locale
        self.model_admin.permission_helper.locale = self.locale
        return super().dispatch(request, *args, **kwargs)

    def get_locale(self, request):
        instance = getattr(self, "instance", None)
        if instance:
            locale = getattr(instance, "locale", None)
        elif "locale" in request.GET:
            locale = Locale.objects.filter(language_code=request.GET["locale"]).first()
        else:
            locale = None
        return locale or Locale.get_active()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["locale"] = self.locale
        context["translations"] = self.get_translations_context_data()
        context["wagtail_version"] = get_main_version()
        return context

    def get_translations_context_data(self):
        return []


class TranslatableIndexView(TranslatableViewMixin, IndexView):
    def get_filters(self, request):
        filters = super().get_filters(request)
        filters[2]["locale"] = self.locale.id
        return filters

    def get_translations_context_data(self):
        return [
            {"locale": x, "url": self.url_helper.get_action_url("index", locale=x)}
            for x in Locale.objects.exclude(id=self.locale.id)
        ]


class TranslatableCreateView(TranslatableViewMixin, CreateView):
    def form_valid(self, form):
        # Attach locale to the created object
        instance = form.save(commit=False)
        instance.locale = self.locale
        instance.save()
        messages.success(
            self.request,
            self.get_success_message(instance),
            buttons=self.get_success_message_buttons(instance),
        )
        log(instance=instance, action="wagtail.create")
        return redirect(self.get_success_url())

    def get_translations_context_data(self):
        return [
            {"locale": x, "url": self.url_helper.get_action_url("create", locale=x)}
            for x in Locale.objects.exclude(id=self.locale.id)
        ]


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
        return context

    def get_translations_context_data(self):
        return [
            {"locale": x.locale, "url": self.url_helper.get_action_url("edit", x.pk)}
            for x in self.instance.get_translations().select_related("locale")
        ]


class TranslatableInspectView(TranslatableViewMixin, InspectView):
    pass


class TranslatableDeleteView(TranslatableViewMixin, DeleteView):
    pass


class TranslatableHistoryView(TranslatableViewMixin, HistoryView):
    pass


class TranslatableChooseParentView(TranslatableViewMixin, ChooseParentView):
    pass
