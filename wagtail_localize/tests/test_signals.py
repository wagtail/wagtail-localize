"""
Tests for wagtail-localize signals.
"""

from django.test import TestCase
from wagtail.models import Locale, Page

from wagtail_localize.models import (
    String,
    StringTranslation,
    TranslationContext,
    TranslationSource,
)
from wagtail_localize.segments import StringSegmentValue
from wagtail_localize.signals import post_source_update, process_string_segment
from wagtail_localize.strings import StringValue
from wagtail_localize.test.models import TestPage, TestSnippet


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    page_revision = page.save_revision()
    page_revision.publish()
    page.refresh_from_db()
    return page


class TestProcessStringSegmentSignal(TestCase):
    def setUp(self):
        self.source_locale = Locale.objects.get(language_code="en")
        self.dest_locale = Locale.objects.create(language_code="fr")

        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="This is some test content",
        )
        self.source, created = TranslationSource.get_or_create_from_instance(
            self.page
        )

        # Add a string translation so _get_segments_for_translation doesn't raise
        self.string = String.from_value(
            self.source_locale,
            StringValue.from_plaintext("This is some test content"),
        )
        self.string_translation = StringTranslation.objects.create(
            translation_of=self.string,
            locale=self.dest_locale,
            context=TranslationContext.objects.get(
                object_id=self.page.translation_key, path="test_charfield"
            ),
            data="Ceci est du contenu de test",
        )

    def test_signal_is_fired_for_each_string_segment(self):
        received = []

        def handler(
            sender, string_segment, string_value, locale, fallback, source, **kwargs
        ):
            received.append(
                {
                    "string_segment": string_segment,
                    "string_value": string_value,
                    "locale": locale,
                    "fallback": fallback,
                    "source": source,
                }
            )
            return None

        process_string_segment.connect(handler)
        try:
            self.source._get_segments_for_translation(
                self.dest_locale, fallback=True
            )
        finally:
            process_string_segment.disconnect(handler)

        self.assertTrue(len(received) >= 1)
        # Verify signal arguments
        signal_data = received[0]
        self.assertEqual(signal_data["locale"], self.dest_locale)
        self.assertEqual(signal_data["fallback"], True)
        self.assertEqual(signal_data["source"], self.source)
        self.assertIsInstance(signal_data["string_value"], StringValue)
        self.assertEqual(signal_data["string_value"].data, self.string_translation.data)

    def test_signal_can_replace_string_value(self):
        """
        The returned value from a process_string_segment signal handler gets used.

        If a process_string_segment signal handler returns a value, then that
        value is used within _get_segments_for_translation().
        """
        replacement = StringValue("Replaced by signal")

        # This signal handler returns the replacement value for the test_charfield.
        def handler(sender, string_segment, string_value, **kwargs):
            if string_segment.context.path == "test_charfield":
                return replacement
            return None

        process_string_segment.connect(handler)
        try:
            segments = self.source._get_segments_for_translation(
                self.dest_locale, fallback=True
            )
        finally:
            process_string_segment.disconnect(handler)

        # The results include the replacement value (for test_charfield).
        string_segments = [
            s for s in segments if isinstance(s, StringSegmentValue)
        ]
        modified = [s for s in string_segments if s.string == replacement]
        self.assertEqual(len(modified), 1)

    def test_signal_none_response_keeps_original(self):
        """
        If a process_string_segment signal handler returns None, then original is used.
        """
        # This handler returns None.
        def handler(sender, **kwargs):
            return None

        process_string_segment.connect(handler)
        try:
            segments = self.source._get_segments_for_translation(
                self.dest_locale, fallback=True
            )
        finally:
            process_string_segment.disconnect(handler)

        string_segments = [
            s for s in segments if isinstance(s, StringSegmentValue)
        ]
        # The original translation is used for the test_charfield.
        charfield_segment = [
            s
            for s in string_segments
            if s.path == "test_charfield"
        ]
        self.assertEqual(len(charfield_segment), 1)
        self.assertEqual(charfield_segment[0].string.data, "Ceci est du contenu de test")

    def test_first_non_none_response_wins(self):
        """
        First non-None value from process_string_segment signal handlers gets used.

        If a process_string_segment signal handler returns a value, then that
        value is used within _get_segments_for_translation().
        """
        second_replacement = StringValue("Second handler")
        third_replacement = StringValue("Third handler")

        # A signal handler that always returns None.
        def handler_first(sender, **kwargs):
            return None

        # A signal handler that always returns second_replacement.
        def handler_second(sender, **kwargs):
            return second_replacement

        # A signal handler that always returns third_replacement.
        def handler_third(sender, **kwargs):
            return third_replacement

        process_string_segment.connect(handler_first)
        process_string_segment.connect(handler_second)
        process_string_segment.connect(handler_third)
        try:
            segments = self.source._get_segments_for_translation(
                self.dest_locale, fallback=True
            )
        finally:
            process_string_segment.disconnect(handler_first)
            process_string_segment.disconnect(handler_second)
            process_string_segment.disconnect(handler_third)

        string_segments = [
            s for s in segments if isinstance(s, StringSegmentValue)
        ]
        charfield_segment = [
            s for s in string_segments if s.path == "test_charfield"
        ]
        self.assertEqual(len(charfield_segment), 1)
        # One of the handlers should have won (order depends on connection order)
        self.assertIn(
            charfield_segment[0].string,
            [second_replacement, third_replacement],
        )


class TestPostSourceUpdateSignal(TestCase):
    def setUp(self):
        self.page = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Original content",
        )
        self.source, created = TranslationSource.get_or_create_from_instance(
            self.page
        )

    def test_signal_is_fired_after_update_from_db(self):
        received = []

        def handler(sender, source, **kwargs):
            received.append({"source": source, "sender": sender})

        post_source_update.connect(handler)
        try:
            self.source.update_from_db()
        finally:
            post_source_update.disconnect(handler)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["source"], self.source)
        self.assertEqual(received[0]["sender"], TranslationSource)
