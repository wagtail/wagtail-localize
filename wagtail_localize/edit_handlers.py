from wagtail.admin.edit_handlers import BaseCompositeEditHandler


def filter_edit_handler(edit_handler, filter_func):
    """
    Traverses an edit handler and runs `filter_func` on each leaf edit handler it finds.

    If that function returns False, that edit handler will be removed.

    CompositeEditHandlers without children are removed automatically.
    """
    if isinstance(edit_handler, BaseCompositeEditHandler):
        edit_handler.children = [
            filter_edit_handler(child_edit_handler, filter_func)
            for child_edit_handler in edit_handler.children
        ]

        edit_handler.children = [
            child_edit_handler
            for child_edit_handler in edit_handler.children
            if child_edit_handler is not None
        ]

        if edit_handler.children:
            return edit_handler
    else:
        if filter_func(edit_handler):
            return edit_handler


def filter_edit_handler_on_instance_bound(edit_handler, filter_func):
    """
    Returns an edit handler class that will filter out fields once an instance is bound.
    """

    def bind_to(self, **kwargs):
        new = super(edit_handler.__class__, self).bind_to(**kwargs)

        if "instance" in kwargs:
            new = filter_edit_handler(
                new, lambda edit_handler: filter_func(edit_handler, kwargs["instance"])
            )

        return new

    edit_handler_class = type(
        "WagtailLocalizeWrapped" + edit_handler.__class__.__name__,
        (edit_handler.__class__,),
        {"bind_to": bind_to},
    )

    return edit_handler_class(**edit_handler.clone_kwargs())
