from django.test import TestCase

from wagtail_localize.segments import SegmentValue
from wagtail_localize.segments.html import (
    extract_html_segments,
    restore_html_segments,
    extract_html_elements,
    restore_html_elements,
)


class TestExtractHTMLSegment(TestCase):
    def test_extract_segments(self):
        template, segments = extract_html_segments(
            """
            <p><b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.</p>
            <p>Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.</p>
            """
        )

        self.assertHTMLEqual(
            template,
            """
            <p><text position="0"></text></p>
            <p><text position="1"></text></p>
            """,
        )

        self.assertEqual(
            segments,
            [
                '<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.',
                'Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.',
            ],
        )

    def test_extract_segments_2(self):
        template, segments = extract_html_segments(
            """
            <h1>Foo bar baz</h1>
            <p>This is a paragraph. <b>This is some bold <i>and now italic</i></b> text</p>
            <p>&lt;script&gt; this should be interpreted as text.</p>
            <ul>
                <li>List item one</li>
                <li><b>List item two</li>
            </ul>
            <img src="foo" alt="This bit isn't translatable">
            """
        )

        self.assertHTMLEqual(
            template,
            """
            <h1><text position="0"></text></h1>
            <p><text position="1"></text></p>
            <p><text position="2"></text></p>
            <ul>
                <li><text position="3"></text></li>
                <li><text position="4"></text></li>
            </ul>
            <img alt="This bit isn\'t translatable" src="foo">
            """,
        )

        self.assertEqual(
            segments,
            [
                "Foo bar baz",
                "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
                "&lt;script&gt; this should be interpreted as text.",
                "List item one",
                "<b>List item two</b>",
            ],
        )


class TestExtractHTMLElements(TestCase):
    def test_extract_html_elements(self):
        text, elements = extract_html_elements(
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"
        )

        self.assertEqual(
            text, "This is a paragraph. This is some bold and now italic text"
        )
        self.assertEqual(elements, [(39, 53, "i", {}), (21, 53, "b", {})])

    def test_special_chars_unescaped(self):
        text, elements = extract_html_elements("<b>foo</b><i> &amp; bar</i>")

        self.assertEqual(text, "foo & bar")
        self.assertEqual(elements, [(0, 3, "b", {}), (3, 9, "i", {})])


class TestRestoreHTMLSegments(TestCase):
    def test_restore_segments(self):
        html = restore_html_segments(
            """
            <p><text position="0"></text></p>
            <p><text position="1"></text></p>
            """,
            [
                '<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.',
                'Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.',
            ]
        )

        self.assertHTMLEqual(
            """
            <p><b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.</p>
            <p>Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.</p>
            """,
            html
        )

    def test_restore_segments_2(self):
        html = restore_html_segments(
            """
            <h1><text position="0"></text></h1>
            <p><text position="1"></text></p>
            <p><text position="2"></text></p>
            <ul>
                <li><text position="3"></text></li>
                <li><text position="4"></text></li>
            </ul>
            <img alt="This bit isn\'t translatable" src="foo">
            """,
            [
                "Foo bar baz",
                "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
                "&lt;script&gt; this should be interpreted as text.",
                "List item one",
                "<b>List item two</b>",
            ]
        )

        self.assertHTMLEqual(
            """
            <h1>Foo bar baz</h1>
            <p>This is a paragraph. <b>This is some bold <i>and now italic</i></b> text</p>
            <p>&lt;script&gt; this should be interpreted as text.</p>
            <ul>
                <li>List item one</li>
                <li><b>List item two</li>
            </ul>
            <img src="foo" alt="This bit isn't translatable">
            """,
            html
        )


class TestRestoreHTMLElements(TestCase):
    def test_restore_html_elements(self):
        html = restore_html_elements(
            "This is a paragraph. This is some bold and now italic text",
            [(39, 53, "i", {}), (21, 53, "b", {})],
        )

        self.assertEqual(
            html,
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )

    def test_special_chars_escaped(self):
        html = restore_html_elements("foo & bar", [(0, 3, "b", {}), (3, 9, "i", {})])

        self.assertEqual(html, "<b>foo</b><i> &amp; bar</i>")


class TestHTMLSegmentValue(TestCase):
    def test_text(self):
        segment = SegmentValue.from_html(
            "foo",
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )
        self.assertEqual(
            segment.text, "This is a paragraph. This is some bold and now italic text"
        )

    def test_html(self):
        segment = SegmentValue.from_html(
            "foo",
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )
        self.assertEqual(
            segment.html,
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )

    def test_html_with_ids(self):
        segment = SegmentValue.from_html(
            "foo",
            '<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.',
        )
        self.assertEqual(
            segment.html_with_ids,
            '<b>Bread</b> is a <a id="a1">staple food</a> prepared from a <a id="a2">dough</a> of <a id="a3">flour</a> and <a id="a4">water</a>, usually by <a id="a5">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of <a id="a6">agriculture</a>.',
        )
