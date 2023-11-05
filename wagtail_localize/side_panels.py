from wagtail.admin.ui.side_panels import PageSidePanels


class LocalizedPageSidePanels(PageSidePanels):
    def __init__(self, request, page, translation):
        super().__init__(
            request,
            page,
            preview_enabled=False,
            comments_enabled=False,
            show_schedule_publishing_toggle=False,
        )
