from django.conf.urls import url
from django.utils.translation import ugettext_lazy
from django.views.generic import DetailView, ListView

from wagtail.admin.viewsets.base import ViewSet
from wagtail.core.permission_policies import ModelPermissionPolicy

from wagtail_localize.translation.models import Translation


class TranslationListView(ListView):
    template_name = "wagtail_localize_translation/management/list.html"
    page_title = ugettext_lazy("Translations")
    context_object_name = "translations"
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    header_icon = ""


class TranslationDetailView(DetailView):
    success_message = ugettext_lazy("Translation '{0}' updated.")
    error_message = ugettext_lazy(
        "The translation could not be saved due to errors."
    )
    context_object_name = "translation"
    template_name = "wagtail_localize_translation/management/detail.html"
    permission_policy = None
    list_url_name = None
    detail_url_name = None
    copy_for_translation_url_name = None
    header_icon = ""

    def get_context_data(self, object):
        context = super().get_context_data(object=object)
        # pages = list(object.pages.order_by("id"))
        # pages_by_id = {page.id: page for page in pages}

        # # Add depths to pages
        # for page in pages:
        #     # Pages are in depth-first-search order so parents are processed before their children
        #     if page.parent_id:
        #         page.depth = pages_by_id[page.parent_id].depth + 1
        #     else:
        #         page.depth = 0

        # context["pages"] = pages

        context["dependencies"] = [
            {
                'object': related_object.object,
                'instance': related_object.object.get_instance_or_none(object.source.locale),
                'translated_instance': related_object.object.get_instance_or_none(object.target_locale),
                'translation_id': related_object.translation_id,
            }

            for related_object in object.source.relatedobjectsegment_set.all().annotate_translation_id(object.target_locale)
        ]

        context["untranslated_dependencies"] = any(dep['translated_instance'] is None for dep in context["dependencies"])

        context["segments"] = [
            segment
            for segment in object.source.stringsegment_set.order_by('order').annotate_translation(object.target_locale)
        ]

        context["untranslated_segments"] = any(segment.translation is None for segment in context["segments"])

        context["num_segments_to_translate"] = len([segment for segment in context["segments"] if segment.translation is None])

        context["ready_for_translation"] = not (context["untranslated_dependencies"] or context["untranslated_segments"])

        return context


class TranslationViewSet(ViewSet):
    icon = "site"

    model = Translation
    permission_policy = ModelPermissionPolicy(Translation)

    list_view_class = TranslationListView
    detail_view_class = TranslationDetailView

    @property
    def list_view(self):
        return self.list_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name("list"),
            detail_url_name=self.get_url_name("detail"),
            header_icon=self.icon,
        )

    @property
    def detail_view(self):
        return self.detail_view_class.as_view(
            model=self.model,
            permission_policy=self.permission_policy,
            list_url_name=self.get_url_name("list"),
            detail_url_name=self.get_url_name("detail"),
            copy_for_translation_url_name=self.get_url_name("copy_for_translation"),
            header_icon=self.icon,
        )

    def get_urlpatterns(self):
        return super().get_urlpatterns() + [
            url(r"^$", self.list_view, name="list"),
            url(r"^(?P<pk>\d+)/$", self.detail_view, name="detail"),
        ]
