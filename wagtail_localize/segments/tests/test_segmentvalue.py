from unittest import TestCase

from wagtail_localize.segments import StringSegmentValue


class TestStringSegmentValue(TestCase):
    def test_segment_value(self):
        segment = StringSegmentValue.from_source_html(
            "foo.bar",
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>',
        )

        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(segment.order, 0)
        self.assertEqual(
            segment.attrs, {"a1": {"href": "http://example.com"}}
        )
        self.assertEqual(
            segment.render_text(),
            "This is some text. <foo> Bold text A link and some more Bold text",
        )
        self.assertEqual(
            segment.render_html(),
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>',
        )

        # .with_order()
        orderred = segment.with_order(123)
        self.assertEqual(segment.order, 0)
        self.assertEqual(orderred.order, 123)
        self.assertEqual(orderred.path, "foo.bar")
        self.assertEqual(orderred.string, segment.string)
        self.assertEqual(orderred.attrs, segment.attrs)

        # .wrap()
        wrapped = segment.wrap("baz")
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(wrapped.path, "baz.foo.bar")
        self.assertEqual(wrapped.order, segment.order)
        self.assertEqual(wrapped.string, segment.string)
        self.assertEqual(wrapped.attrs, segment.attrs)

        # .unwrap()
        path_component, unwrapped = segment.unwrap()
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(path_component, "foo")
        self.assertEqual(unwrapped.path, "bar")
        self.assertEqual(unwrapped.order, segment.order)
        self.assertEqual(unwrapped.string, segment.string)
        self.assertEqual(unwrapped.attrs, segment.attrs)

    def test_replace_html_attrs(self):
        segment = StringSegmentValue.from_source_html(
            "foo.bar",
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a id="a1">A link and some more <b>Bold text</b></a>',
        )

        segment.attrs = {"a1": {"href": "http://changed-example.com"}}

        self.assertEqual(
            segment.render_html(),
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://changed-example.com">A link and some more <b>Bold text</b></a>',
        )
