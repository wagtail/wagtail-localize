from django.test import TestCase

from wagtail_localize.strings import StringValue, extract_strings, restore_strings


class TestStringValueFromSourceHTML(TestCase):
    def test_string_from_html(self):
        string, attrs = StringValue.from_source_html(
            '<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>'
        )

        self.assertEqual(
            string.data,
            '<b>Bread</b> is a <a id="a1">staple food</a> prepared from a <a id="a2">dough</a> of <a id="a3">flour</a> and <a id="a4">water</a>',
        )

        self.assertEqual(
            attrs,
            {
                'a1': {'href': 'https://en.wikipedia.org/wiki/Staple_food'},
                'a2': {'href': 'https://en.wikipedia.org/wiki/Dough'},
                'a3': {'href': 'https://en.wikipedia.org/wiki/Flour'},
                'a4': {'href': 'https://en.wikipedia.org/wiki/Water'},
            }
        )

    def test_validation(self):
        # All of these should be allowed
        StringValue.from_source_html("Foo bar baz")
        StringValue.from_source_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text")
        StringValue.from_source_html("&lt;script&gt; this should be interpreted as text.")
        StringValue.from_source_html("Foo<br/>bar<br/>baz")
        StringValue.from_source_html('<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>')

    def test_block_tags_not_allowed(self):
        with self.assertRaises(ValueError) as e:
            StringValue.from_source_html("<p>Foo bar baz</p>")

        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(e.exception.args, ('<p> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)',))

        with self.assertRaises(ValueError) as e:
            StringValue.from_source_html("<img/>")

        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(e.exception.args, ('<img> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)',))


class TestStringValueFromTranslatedHTML(TestCase):
    def test_validation(self):
        # All of these should be allowed
        StringValue.from_translated_html("Foo bar baz")
        StringValue.from_translated_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text")
        StringValue.from_translated_html("&lt;script&gt; this should be interpreted as text.")
        StringValue.from_translated_html("Foo<br/>bar<br/>baz")
        StringValue.from_translated_html('<a id="1">staple food</a>')

    def test_block_tags_not_allowed(self):
        with self.assertRaises(ValueError) as e:
            StringValue.from_translated_html("<p>Foo bar baz</p>")

        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(e.exception.args, ('<p> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)',))

        with self.assertRaises(ValueError) as e:
            StringValue.from_translated_html("<img/>")

        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(e.exception.args, ('<img> tag is not allowed. Strings can only contain standard HTML inline tags (such as <b>, <a>)',))

    def test_attributes_not_allowed(self):
        with self.assertRaises(ValueError) as e:
            StringValue.from_translated_html('<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>')

        self.assertIsInstance(e.exception, ValueError)
        self.assertEqual(e.exception.args, ("Strings cannot have any HTML tags with attributes (except for 'id' in <a> tags)",))


class TestStringValueFromPlaintext(TestCase):
    def test_string_from_plaintext(self):
        string = StringValue.from_plaintext(
            "This is a test, \"foo\" bar 'baz'.!?;:",
        )

        self.assertEqual(
            string.data,
            "This is a test, \"foo\" bar 'baz'.!?;:",
        )

    def test_special_chars_escaped(self):
        string = StringValue.from_plaintext("<Foo> & bar")

        self.assertEqual(string.data, "&lt;Foo&gt; &amp; bar")

    def test_unicode_chars_not_escaped(self):
        # unicode characters should not be escaped as this would be horrible for translators!
        string = StringValue.from_plaintext("セキレイ")
        self.assertEqual(string.data, "セキレイ")

    def test_newlines_converted_to_br_tags(self):
        string = StringValue.from_plaintext("foo\nbar\nbaz")
        self.assertEqual(string.data, "foo<br/>bar<br/>baz")

        string = StringValue.from_plaintext("\nfoo\nbar\n")
        self.assertEqual(string.data, "<br/>foo<br/>bar<br/>")


class TestRenderHTML(TestCase):
    maxDiff = None

    def test_render_html(self):
        # Note, I swapped the first two links around to check that the attrs are restored to the correct one
        string = StringValue(
            '<b>Bread</b> is a <a id="a2">dough</a> prepared from a <a id="a1">staple food</a> of <a id="a3">flour</a> and <a id="a4">water</a>',
        )

        attrs = {
            'a1': {'href': 'https://en.wikipedia.org/wiki/Staple_food'},
            'a2': {'href': 'https://en.wikipedia.org/wiki/Dough'},
            'a3': {'href': 'https://en.wikipedia.org/wiki/Flour'},
            'a4': {'href': 'https://en.wikipedia.org/wiki/Water'},
        }

        self.assertEqual(
            string.render_html(attrs),
            '<b>Bread</b> is a <a href="https://en.wikipedia.org/wiki/Dough">dough</a> prepared from a <a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a> of <a href="https://en.wikipedia.org/wiki/Flour">flour</a> and <a href="https://en.wikipedia.org/wiki/Water">water</a>',
        )


class TestStringRenderText(TestCase):
    def test_string_render_text(self):
        string = StringValue(
            "This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"
        )

        self.assertEqual(
            string.render_text(), "This is a paragraph. This is some bold and now italic text"
        )

    def test_special_chars_unescaped(self):
        string = StringValue("<b>foo</b><i> &amp; bar</i>")
        self.assertEqual(string.render_text(), "foo & bar")

    def test_br_tags_converted_to_newlines(self):
        string = StringValue("foo<br>bar<br>baz")
        self.assertEqual(string.render_text(), "foo\nbar\nbaz")

        string = StringValue("<br/><b>foo</b><br/><i>bar</i><br/>")
        self.assertEqual(string.render_text(), "\nfoo\nbar\n")


class TextExtractStrings(TestCase):
    def test_extract_strings(self):
        template, strings = extract_strings(
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
            strings,
            [
                StringValue.from_source_html('<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.'),
                StringValue.from_source_html('Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.'),
            ],
        )

    def test_extract_strings_2(self):
        template, strings = extract_strings(
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
            strings,
            [
                StringValue.from_source_html("Foo bar baz"),
                StringValue.from_source_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"),
                StringValue.from_source_html("&lt;script&gt; this should be interpreted as text."),
                StringValue.from_source_html("List item one"),
                StringValue.from_source_html("List item two"),
            ],
        )

    def test_block_tag_in_inline_tag(self):
        # If an inline tag contains a block tag. The inline tag must be in the template.
        # Testing for issue https://github.com/mozilla/donate-wagtail/issues/586
        template, strings = extract_strings("<p><i>Foo <p>Bar</p></i></p>")

        self.assertHTMLEqual(
            template,
            '<p><i><text position="0"></text> <p><text position="1"></text></p></i></p>',
        )

        self.assertEqual(strings, [
            StringValue.from_source_html("Foo"),
            StringValue.from_source_html("Bar")
        ])

    def test_br_tag_is_treated_as_inline_tag(self):
        template, strings = extract_strings(
            "<p><b>Foo <i>Bar<br/>Baz</i></b></p>"
        )

        self.assertHTMLEqual(template, '<p><b><text position="0"></text></b></p>')

        self.assertEqual(strings, [
            StringValue.from_source_html("Foo <i>Bar<br/>Baz</i>")
        ])

    def test_br_tag_is_removed_when_it_appears_at_beginning_of_segment(self):
        template, strings = extract_strings("<p><i><br/>Foo</i></p>")

        self.assertHTMLEqual(template, '<p><i><br/><text position="0"></text></i></p>')

        self.assertEqual(strings, [StringValue.from_source_html("Foo")])

    def test_br_tag_is_removed_when_it_appears_at_end_of_segment(self):
        template, strings = extract_strings("<p><i>Foo</i><br/></p>")

        self.assertHTMLEqual(template, '<p><i><text position="0"></text></i><br/></p>')

        self.assertEqual(strings, [StringValue.from_source_html("Foo")])

    def test_empty_inline_tag(self):
        template, strings = extract_strings("<p><i></i>Foo</p>")

        self.assertHTMLEqual(template, '<p><i></i><text position="0"></text></p>')

        self.assertEqual(strings, [StringValue.from_source_html("Foo")])


class TestRestoreStrings(TestCase):
    def test_restore_strings(self):
        html = restore_strings(
            """
            <p><text position="0"></text></p>
            <p><text position="1"></text></p>
            """,
            [
                StringValue.from_source_html('<b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.'),
                StringValue.from_source_html('Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.'),
            ],
        )

        self.assertHTMLEqual(
            """
            <p><b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple food</a>\xa0prepared from a\xa0<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history it has been popular around the world and is one of the oldest artificial foods, having been of importance since the dawn of\xa0<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.</p>
            <p>Proportions of types of flour and other ingredients vary widely, as do modes of preparation. As a result, types, shapes, sizes, and textures of breads differ around the world. Bread may be\xa0<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as reliance on naturally occurring\xa0<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, industrially produced yeast, or high-pressure aeration. Some bread is cooked before it can leaven, including for traditional or religious reasons. Non-cereal ingredients such as fruits, nuts and fats may be included. Commercial bread commonly contains additives to improve flavor, texture, color, shelf life, and ease of manufacturing.</p>
            """,
            html,
        )

    def test_restore_strings_2(self):
        html = restore_strings(
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
                StringValue.from_source_html("Foo bar baz"),
                StringValue.from_source_html("This is a paragraph. <b>This is some bold <i>and now italic</i></b> text"),
                StringValue.from_source_html("&lt;script&gt; this should be interpreted as text."),
                StringValue.from_source_html("List item one"),
                StringValue.from_source_html("<b>List item two</b>"),
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
