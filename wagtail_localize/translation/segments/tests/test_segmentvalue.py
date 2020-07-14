from unittest import TestCase

from wagtail_localize.translation.segments import SegmentValue
from wagtail_localize.translation.segments.html import HTMLSnippet


class TestSegmentValue(TestCase):
    def test_segment_value(self):
        segment = SegmentValue(
            "foo.bar",
            HTMLSnippet.from_html('This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>'),
            HTMLSnippet.from_html('Ceci est du texte. &lt;foo&gt; <b>Texte en gras</b> <a href="http://example.com">Un lien et du <b>texte en gras</b></a>'),
        )

        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(segment.order, 0)
        self.assertEqual(
            segment.source.text,
            "This is some text. <foo> Bold text A link and some more Bold text",
        )
        self.assertEqual(
            segment.source.entities,
            [
                HTMLSnippet.Entity(25, 34, "b1", ("b", {})),
                HTMLSnippet.Entity(56, 65, "b2", ("b", {})),
                HTMLSnippet.Entity(
                    35, 65, "a1", ("a", {"href": "http://example.com"})
                ),
            ],
        )
        self.assertEqual(
            segment.source.html,
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>',
        )
        self.assertEqual(
            segment.source.html_with_ids,
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a id="a1">A link and some more <b>Bold text</b></a>',
        )
        self.assertEqual(
            segment.source.get_html_attrs(), {"a#a1": {"href": "http://example.com"}}
        )

        # .with_order()
        orderred = segment.with_order(123)
        self.assertEqual(segment.order, 0)
        self.assertEqual(orderred.order, 123)
        self.assertEqual(orderred.path, "foo.bar")
        self.assertEqual(orderred.source, segment.source)
        self.assertEqual(orderred.translation, segment.translation)

        # .wrap()
        wrapped = segment.wrap("baz")
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(wrapped.path, "baz.foo.bar")
        self.assertEqual(wrapped.order, segment.order)
        self.assertEqual(wrapped.source, segment.source)
        self.assertEqual(wrapped.translation, segment.translation)

        # .unwrap()
        path_component, unwrapped = segment.unwrap()
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(path_component, "foo")
        self.assertEqual(unwrapped.path, "bar")
        self.assertEqual(unwrapped.order, segment.order)
        self.assertEqual(unwrapped.source, segment.source)
        self.assertEqual(unwrapped.translation, segment.translation)
