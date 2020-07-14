from django.test import TestCase

from wagtail_localize.translation.segments.html import (
    extract_html_snippets,
    restore_html_snippets,
    HTMLSnippet,
)


class TestExtractHTMLSnippets(TestCase):
    def test_extract_snippets(self):
        template, snippets = extract_html_snippets(
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
            snippets,
            [
                HTMLSnippet.from_html('<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.'),
                HTMLSnippet.from_html('Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.'),
            ],
        )

    def test_extract_snippets_2(self):
        template, snippets = extract_html_snippets(
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
                <li><b><text position="4"></text></b></li>
            </ul>
            <img alt="This bit isn\'t translatable" src="foo">
            """,
        )

        self.assertEqual(
            snippets,
            [
                HTMLSnippet.from_html("Foo bar baz"),
                HTMLSnippet.from_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"),
                HTMLSnippet.from_html("&lt;script&gt; this should be interpreted as text."),
                HTMLSnippet.from_html("List item one"),
                HTMLSnippet.from_html("List item two"),
            ],
        )

    def test_block_tag_in_inline_tag(self):
        # If an inline tag contains a block tag. The inline tag must be in the template.
        # Testing for issue https://github.com/mozilla/donate-wagtail/issues/586
        template, snippets = extract_html_snippets("<p><i>Foo <p>Bar</p></i></p>")

        self.assertHTMLEqual(
            template,
            '<p><i><text position="0"></text> <p><text position="1"></text></p></i></p>',
        )

        self.assertEqual(snippets, [HTMLSnippet.from_html("Foo"), HTMLSnippet.from_html("Bar")])

    def test_br_tag_is_treated_as_inline_tag(self):
        template, snippets = extract_html_snippets(
            "<p><b>Foo <i>Bar<br/>Baz</i></b></p>"
        )

        self.assertHTMLEqual(template, '<p><b><text position="0"></text></b></p>')

        self.assertEqual(snippets, [HTMLSnippet.from_html("Foo <i>Bar<br/>Baz</i>")])

    def test_br_tag_is_removed_when_it_appears_at_beginning_of_segment(self):
        template, snippets = extract_html_snippets("<p><i><br/>Foo</i></p>")

        self.assertHTMLEqual(template, '<p><i><br/><text position="0"></text></i></p>')

        self.assertEqual(snippets, [HTMLSnippet.from_html("Foo")])

    def test_br_tag_is_removed_when_it_appears_at_end_of_segment(self):
        template, snippets = extract_html_snippets("<p><i>Foo</i><br/></p>")

        self.assertHTMLEqual(template, '<p><i><text position="0"></text></i><br/></p>')

        self.assertEqual(snippets, [HTMLSnippet.from_html("Foo")])

    def test_empty_inline_tag(self):
        template, snippets = extract_html_snippets("<p><i></i>Foo</p>")

        self.assertHTMLEqual(template, '<p><i></i><text position="0"></text></p>')

        self.assertEqual(snippets, [HTMLSnippet.from_html("Foo")])


class TestRestoreHTMLSnippets(TestCase):
    def test_restore_snippets(self):
        html = restore_html_snippets(
            """
            <p><text position="0"></text></p>
            <p><text position="1"></text></p>
            """,
            [
                HTMLSnippet.from_html('<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.'),
                HTMLSnippet.from_html('Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.'),
            ],
        )

        self.assertHTMLEqual(
            """
            <p><b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.</p>
            <p>Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.</p>
            """,
            html,
        )

    def test_restore_segments_2(self):
        html = restore_html_snippets(
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
                HTMLSnippet.from_html("Foo bar baz"),
                HTMLSnippet.from_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"),
                HTMLSnippet.from_html("&lt;script&gt; this should be interpreted as text."),
                HTMLSnippet.from_html("List item one"),
                HTMLSnippet.from_html("<b>List item two</b>"),
            ],
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
            html,
        )


class TestHTMLSnippet(TestCase):
    def test_extract_html_entities(self):
        text, elements = HTMLSnippet._extract_html_entities(
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"
        )

        self.assertEqual(
            text, "This is a paragraph. This is some bold and now italic text"
        )
        self.assertEqual(elements, [(39, 53, "i", {}), (21, 53, "b", {})])

    def test_special_chars_unescaped(self):
        text, elements = HTMLSnippet._extract_html_entities("<b>foo</b><i> &amp; bar</i>")

        self.assertEqual(text, "foo & bar")
        self.assertEqual(elements, [(0, 3, "b", {}), (3, 9, "i", {})])

    def test_restore_html_entities(self):
        html = HTMLSnippet._restore_html_entities(
            "This is a paragraph. This is some bold and now italic text",
            [(39, 53, "i", {}), (21, 53, "b", {})],
        )

        self.assertEqual(
            html,
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )

    def test_special_chars_escaped(self):
        html = HTMLSnippet._restore_html_entities("foo & bar", [(0, 3, "b", {}), (3, 9, "i", {})])

        self.assertEqual(html, "<b>foo</b><i> &amp; bar</i>")

    def test_text(self):
        snippet = HTMLSnippet.from_html(
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )
        self.assertEqual(
            snippet.text, "This is a paragraph. This is some bold and now italic text"
        )

    def test_html(self):
        snippet = HTMLSnippet.from_html(
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )
        self.assertEqual(
            snippet.html,
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text",
        )

    def test_html_with_ids(self):
        snippet = HTMLSnippet.from_html(
            '<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.',
        )
        self.assertEqual(
            snippet.html_with_ids,
            '<b>Bread</b> is a <a id="a1">staple food</a> prepared from a <a id="a2">dough</a> of <a id="a3">flour</a> and <a id="a4">water</a>, usually by <a id="a5">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of <a id="a6">agriculture</a>.',
        )

    def test_replace_html_attrs(self):
        snippet = HTMLSnippet.from_html(
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a id="a1">A link and some more <b>Bold text</b></a>',
        )

        snippet.replace_html_attrs({"a#a1": {"href": "http://changed-example.com"}})

        self.assertEqual(
            snippet.html,
            'This is some text. &lt;foo&gt; <b>Bold text</b> <a href="http://changed-example.com">A link and some more <b>Bold text</b></a>',
        )
