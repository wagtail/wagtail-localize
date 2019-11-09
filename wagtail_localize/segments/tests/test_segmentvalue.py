from unittest import TestCase

from wagtail_localize.segments import SegmentValue


class TestSegmentValue(TestCase):
    def test_segment_value(self):
        segment = SegmentValue.from_html(
            "foo.bar",
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>',
        )

        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(segment.order, 0)
        self.assertEqual(
            segment.text,
            "This is some text. <foo> Bold text A link and some more Bold text",
        )
        self.assertEqual(
            segment.html_elements,
            [
                SegmentValue.HTMLElement(25, 34, "b1", ("b", {})),
                SegmentValue.HTMLElement(56, 65, "b2", ("b", {})),
                SegmentValue.HTMLElement(
                    35, 65, "a1", ("a", {"href": "http://example.com"})
                ),
            ],
        )
        self.assertEqual(
            segment.html,
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://example.com">A link and some more <b>Bold text</b></a>',
        )
        self.assertEqual(
            segment.html_with_ids,
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a id="a1">A link and some more <b>Bold text</b></a>',
        )

        # .with_order()
        orderred = segment.with_order(123)
        self.assertEqual(segment.order, 0)
        self.assertEqual(orderred.order, 123)
        self.assertEqual(orderred.path, "foo.bar")
        self.assertEqual(orderred.text, segment.text)
        self.assertEqual(orderred.html_elements, segment.html_elements)
        self.assertEqual(orderred.html, segment.html)
        self.assertEqual(orderred.html_with_ids, segment.html_with_ids)

        # .wrap()
        wrapped = segment.wrap("baz")
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(wrapped.path, "baz.foo.bar")
        self.assertEqual(wrapped.order, segment.order)
        self.assertEqual(wrapped.text, segment.text)
        self.assertEqual(wrapped.html_elements, segment.html_elements)
        self.assertEqual(wrapped.html, segment.html)
        self.assertEqual(wrapped.html_with_ids, segment.html_with_ids)

        # .unwrap()
        path_component, unwrapped = segment.unwrap()
        self.assertEqual(segment.path, "foo.bar")
        self.assertEqual(path_component, "foo")
        self.assertEqual(unwrapped.path, "bar")
        self.assertEqual(unwrapped.order, segment.order)
        self.assertEqual(unwrapped.text, segment.text)
        self.assertEqual(unwrapped.html_elements, segment.html_elements)
        self.assertEqual(unwrapped.html, segment.html)
        self.assertEqual(unwrapped.html_with_ids, segment.html_with_ids)
