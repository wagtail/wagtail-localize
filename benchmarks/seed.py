"""Build benchmark content without requiring Django at import time.

Each execution uses a fresh database, so these helpers create but never clear
data.
"""

TARGET_LANGUAGES = ["en", "fr", "es"]
HOME_SLUG = "bench-home"
# Spread leaf pages across a small, non-flat tree.
CATEGORY_COUNT = 4


def ensure_locales():
    """Every locale the fixture needs. Idempotent."""
    from wagtail.models import Locale

    return {
        code: Locale.objects.get_or_create(language_code=code)[0]
        for code in TARGET_LANGUAGES
    }


def build_snippet_pool(count, locale):
    """Create reusable translatable snippets referenced by benchmark pages."""
    from tests.testapp.models import TestSnippet

    return [
        TestSnippet.objects.create(
            field=f"Snippet {i} body — translatable text.",
            small_charfield=f"tag-{i}"[:10],
            locale=locale,
        )
        for i in range(count)
    ]


def build_tree(pages, locale, snippets):
    """Build a categorized tree and return its home and flat leaf-page list."""
    from wagtail.models import Page

    from tests.testapp.models import TestHomePage, TestPage

    root = Page.objects.get(depth=1)
    home = root.add_child(
        instance=TestHomePage(title="Bench Home", slug=HOME_SLUG, locale=locale)
    )
    categories = [
        home.add_child(
            instance=TestPage(
                title=f"Category {c}", slug=f"bench-category-{c}", locale=locale
            )
        )
        for c in range(CATEGORY_COUNT)
    ]

    pages_list = []
    for i in range(pages):
        category = categories[i % CATEGORY_COUNT]
        page = category.add_child(
            instance=TestPage(
                title=f"Page {i}",
                slug=f"bench-page-{i}",
                locale=locale,
                test_snippet=snippets[i % len(snippets)],
                test_richtextfield=(
                    f"<p>Body text for page {i}. This paragraph is "
                    f"translatable prose that produces a segment.</p>"
                ),
            )
        )
        pages_list.append(page)

    return home, pages_list
