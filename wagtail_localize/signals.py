"""
Signals for extending wagtail-localize behavior.

These signals allow third-party packages to easily hook into wagtail-localize's
segment processing.
"""

from django.dispatch import Signal

# Sent for each string segment during TranslationSource._get_segments_for_translation().
# Receivers can return a modified StringValue to change the translation.
#
# Arguments:
#   sender: TranslationSource class
#   string_segment: StringSegment instance being processed
#   string_value: StringValue that will be used (can be modified or replaced)
#   locale: Target Locale instance
#   fallback: Boolean indicating if fallback mode is enabled
#   source: TranslationSource instance
#
# Return: StringValue to use, or None to keep the original
process_string_segment = Signal()

# Sent after TranslationSource.update_from_db() completes successfully.
# Useful for post-processing after source content has been synced.
#
# Arguments:
#   sender: TranslationSource class
#   source: TranslationSource instance that was updated
post_source_update = Signal()
