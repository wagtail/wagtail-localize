from django.urls import reverse
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin.ui.side_panels import PagePreviewSidePanel, PageSidePanels
from wagtail.models import PreviewableMixin


class LocalizedPreviewSidePanel(PagePreviewSidePanel):
    def __init__(self, object, request, translation):
        super().__init__(object, request)
        self.translation = translation

    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)

        if isinstance(object, PreviewableMixin) and object.is_previewable():
            preview_modes = [
                {
                    "mode": mode,
                    "label": label,
                    "url": reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.translation.id],
                    )
                    if mode == self.object.default_preview_mode
                    else reverse(
                        "wagtail_localize:preview_translation",
                        args=[self.translation.id, mode],
                    ),
                }
                for mode, label in self.object.preview_modes
            ]
        else:
            preview_modes = []

        for mode in preview_modes:
            context["preview_url"] = mode["url"]

        return context


class LocalizedPageSidePanels(PageSidePanels):
    def __init__(self, request, page, translation):
        if WAGTAIL_VERSION >= (4, 1):
            super().__init__(
                request,
                page,
                preview_enabled=False,
                comments_enabled=False,
                show_schedule_publishing_toggle=False,
            )
        else:
            super().__init__(
                request, page, preview_enabled=False, comments_enabled=False
            )

        # FIXME: enable the preview panels, with an updated JS handler, as preview-panels.js expects a regular form
        # self.side_panels += [
        #     LocalizedPreviewSidePanel(page, self.request, translation),
        # ]
