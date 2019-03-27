import functools

from wagtail.core import hooks

from .html import HTMLSegmentFormatter


@functools.lru_cache()
def get_segment_formatter_classes():
    formatter_classes = {
        'html': HTMLSegmentFormatter,
    }

    for fn in hooks.get_hooks('wagtail_i18n_register_segment_formatter'):
        new_formatter_classes = fn()
        if new_formatter_classes:
            formatter_classes.update(new_formatter_classes)

    return formatter_classes

def get_segment_formatter_class(format_name):
    return get_segment_formatter_classes()[format_name]
