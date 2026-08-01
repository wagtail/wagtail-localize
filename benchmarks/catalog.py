"""The catalog of wagtail-localize flows the harness measures.

This module declares WHAT is measured. It runs no measurement, imports no
measuring tool, and defers every Django import into a function — so importing
it, and printing the catalog, costs nothing and needs no database.

Coverage is not exhaustive and must not be assumed to be. A flow belongs here
when it represents a process worth watching; anything absent is absent on
purpose or not yet added.

A Flow is one process. A Flow that compares scales declares its ScalePoints,
and the runner expands the pair into one execution per point. A Flow without
scale points runs once, with size None.
"""

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScalePoint:
    """One input size a flow is measured at.

    `expected_workload` is the amount of work this size is supposed to produce,
    counted in the flow's `workload_unit`. It is data rather than a check
    buried inside verify() so the catalog can be read, listed and tested
    without executing anything — and so a scenario that quietly stops
    producing its workload fails loudly instead of measuring a smaller one.
    """

    label: str
    why: str
    expected_workload: int


@dataclass(frozen=True)
class Flow:
    """One process worth measuring, plus the metadata that makes it legible.

    `run` performs the operation and returns its raw artifacts — a response, a
    list of responses, or None. It does not count, parse or query: it executes
    inside the measured region, so anything it does lands in the numbers.

    `verify` runs after the measurement is closed. It may parse artifacts and
    query freely. It raises if the scenario did not really happen, and returns
    the observed workload for flows that declare a unit.

    `setup`, when present, establishes the expected prior state before the
    measurement and raises if the fixture is not in it.
    """

    name: str
    group: str
    why: str
    entrypoint: str
    covers: tuple[str, ...]
    run: Callable[[Any, str | None], Any]
    verify: Callable[[Any, str | None, Any], int | None]
    workload_unit: str | None = None
    scale_points: tuple[ScalePoint, ...] = ()
    setup: Callable[[Any, str | None], None] | None = None

    def sizes(self):
        """The size labels this flow expands to. A flow without scale points
        yields a single execution whose size is None."""
        return tuple(point.label for point in self.scale_points) or (None,)

    def scale_point(self, size):
        for point in self.scale_points:
            if point.label == size:
                return point
        return None


# ---------------------------------------------------------------------------
# Fixture
#
# Sizes are fixed. Big enough to fan out across snippets and locales, small
# enough to build in a second or two.
# ---------------------------------------------------------------------------

PAGES = 12
SNIPPETS = 4
# Extra pages the core operations flows walk, kept disjoint from the pages the
# admin flows act on so they do not collide with each other's preconditions.
CORE_PAGES = 5
# Page translations pre-created so the report view renders several rows.
REPORT_PAGE_TRANSLATIONS = 5
# StreamField blocks loaded onto the dedicated heavy page, so the flows that
# scale with segment count fan out over many segments instead of the handful an
# ordinary page carries.
REFRESH_SEGMENT_BLOCKS = 40
# How many segments the per-segment save flow writes at each size.
STRING_SAVES_SMALL = 5
STRING_SAVES_LARGE = REFRESH_SEGMENT_BLOCKS


def _admin_client():
    """A logged-in superuser client, so admin views authorize normally."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    user_model = get_user_model()
    user, _created = user_model.objects.update_or_create(
        username="benchmark-admin",
        defaults={
            "email": "benchmark-admin@example.com",
            "is_staff": True,
            "is_active": True,
            "is_superuser": True,
        },
    )
    client = Client()
    client.force_login(user)
    return client, user


def _create_translation(instance, target_locale, *, user=None):
    """Give `instance` a real, published target translation, so the flows that
    act on an existing translation have one."""
    from wagtail_localize.models import Translation, TranslationSource

    source, _created = TranslationSource.get_or_create_from_instance(instance)
    translation, _created = Translation.objects.get_or_create(
        source=source,
        target_locale=target_locale,
        defaults={"enabled": True},
    )
    translation.save_target(user=user, publish=True)
    return source, translation


def _target_page_id(translation):
    """The id of the translated page a Translation produced.

    The editor is Wagtail's own page-edit view, intercepted for the target
    page, so the editor flows need the target's id and not the source's.
    """
    return translation.get_target_instance().id


def _segment_ids(source):
    """A source's StringSegment ids in page order, resolved during setup so the
    flows that save segments do not spend measured queries finding them."""
    from wagtail_localize.models import StringSegment

    return list(
        StringSegment.objects.filter(source=source)
        .order_by("order")
        .values_list("id", flat=True)
    )


def prepare():
    """Build the fixture for one execution.

    Runs in a child process holding a fresh copy of an empty migrated database,
    so it never has to clear anything and results do not depend on execution
    order.

    Slices are disjoint across roles so flows do not collide with each other's
    preconditions:

        pages:    [0]        existing_page
                  [1:5]      extra report-only translations
                  [5:10]     core_pages, untouched by the admin flows
                  [10]       heavy StreamField page, shared by every `large`
                  [11]       submit_page, left untranslated
        snippets: [0]        existing_snippet
                  [1]        extra report-only translation
                  [3]        submit_snippet, left untranslated
    """
    from benchmarks.seed import build_snippet_pool, build_tree, ensure_locales

    locales = ensure_locales()
    snippets = build_snippet_pool(SNIPPETS, locales["en"])
    _home, pages = build_tree(PAGES, locales["en"], snippets)
    client, user = _admin_client()

    existing_page = pages[0]
    existing_page_source, existing_page_translation = _create_translation(
        existing_page, locales["fr"], user=user
    )
    existing_snippet = snippets[0]
    existing_snippet_source, existing_snippet_translation = _create_translation(
        existing_snippet, locales["fr"], user=user
    )

    # Extra translations so the report view has several rows across content
    # types, not just the "existing" ones above.
    for page in pages[1:REPORT_PAGE_TRANSLATIONS]:
        _create_translation(page, locales["fr"], user=user)
    _create_translation(snippets[1], locales["fr"], user=user)

    # Shared heavy fixture for every large flow; its Translation and target are
    # also visible to report and tree-sync. Publish the blocks before creating
    # the source, because segments come from stored source content, not the
    # live page. Editor flows need the Translation and its target, not only a
    # TranslationSource.
    heavy_page = pages[10]
    heavy_page.test_streamfield = [
        ("test_charblock", f"Heavy segment block {i}")
        for i in range(REFRESH_SEGMENT_BLOCKS)
    ]
    heavy_page.save_revision().publish()
    heavy_page_source, heavy_page_translation = _create_translation(
        heavy_page, locales["fr"], user=user
    )

    # Relative properties shared by the fixture: enough segments to save, and a
    # large page genuinely larger than the small one. Exact cardinalities belong
    # to ScalePoint.expected_workload instead, so a model change fails visibly
    # and forces a look at the catalog rather than measuring a smaller workload
    # unnoticed.
    small_segment_ids = _segment_ids(existing_page_source)
    large_segment_ids = _segment_ids(heavy_page_source)
    if len(large_segment_ids) < STRING_SAVES_LARGE:
        raise RuntimeError(
            f"The heavy benchmark page yields {len(large_segment_ids)} string "
            f"segments, fewer than the {STRING_SAVES_LARGE} the large flows "
            f"need. Check REFRESH_SEGMENT_BLOCKS and that the block type still "
            f"extracts one segment per block."
        )
    if len(large_segment_ids) <= len(small_segment_ids):
        raise RuntimeError(
            f"The large benchmark page ({len(large_segment_ids)} segments) "
            f"must yield more segments than the small one "
            f"({len(small_segment_ids)}), or the two sizes measure the same "
            f"thing and no slope is observable."
        )

    return SimpleNamespace(
        locales=locales,
        client=client,
        user=user,
        pages=pages,
        snippets=snippets,
        existing_page=existing_page,
        existing_page_source=existing_page_source,
        existing_page_translation=existing_page_translation,
        existing_snippet=existing_snippet,
        existing_snippet_source=existing_snippet_source,
        existing_snippet_translation=existing_snippet_translation,
        heavy_page=heavy_page,
        heavy_page_source=heavy_page_source,
        heavy_page_translation=heavy_page_translation,
        small_target_page_id=_target_page_id(existing_page_translation),
        large_target_page_id=_target_page_id(heavy_page_translation),
        small_segment_ids=small_segment_ids,
        large_segment_ids=large_segment_ids,
        submit_page=pages[-1],
        submit_snippet=snippets[-1],
        core_pages=pages[5 : 5 + CORE_PAGES],
    )


# ---------------------------------------------------------------------------
# submit_page_post
# ---------------------------------------------------------------------------


def _translation_source(instance):
    """The instance's TranslationSource, or None."""
    from wagtail_localize.models import TranslationSource

    return TranslationSource.objects.filter(
        object_id=instance.translation_key, locale=instance.locale
    ).first()


def _translation_to(instance, locale):
    """The instance's Translation into `locale`, or None.

    Translated variants share a translation_key, so the source locale has to be
    named too, or this matches a translation made from a different variant.
    """
    from wagtail_localize.models import Translation

    return Translation.objects.filter(
        source__object_id=instance.translation_key,
        source__locale=instance.locale,
        target_locale=locale,
    ).first()


def _submit_page_setup(ctx, size):
    """Assert the state the flow starts from, without changing it.

    The page and its snippet must be untranslated, or the POST reconciles an
    existing translation instead of creating one and the flow measures a
    different operation than it names.
    """
    if size is not None:
        raise RuntimeError(f"submit_page_post takes no size; got {size!r}.")

    page, snippet, french = ctx.submit_page, ctx.submit_snippet, ctx.locales["fr"]

    if page.test_snippet_id != snippet.pk:
        raise RuntimeError(
            f"submit_page references snippet {page.test_snippet_id}, not "
            f"submit_snippet ({snippet.pk}). The flow measures the related "
            f"object fan-out, so the two have to be connected."
        )

    for label, instance in (("page", page), ("snippet", snippet)):
        if _translation_source(instance) is not None:
            raise RuntimeError(f"the {label} already has a TranslationSource.")
        if _translation_to(instance, french) is not None:
            raise RuntimeError(f"the {label} is already translated into French.")
        if instance.get_translation_or_none(french) is not None:
            raise RuntimeError(f"the {label} already has a French target.")


def _submit_page_run(ctx, size):
    """POST the submit-translation form, and return the response unexamined."""
    from django.urls import reverse

    return ctx.client.post(
        reverse(
            "wagtail_localize:submit_page_translation",
            args=[ctx.submit_page.id],
        ),
        {"locales": [ctx.locales["fr"].id]},
    )


def _submit_page_verify(ctx, size, response):
    """Check the page and its related snippet were both translated.

    Queries name the object and locale rather than counting rows: prepare()
    creates other translations, so a global count would pass whatever this POST
    did. Returns None — the flow declares no workload, and the objects created
    here are the shape of the operation, not a scale dimension.
    """
    from django.urls import reverse

    if response.status_code != 302:
        raise RuntimeError(
            f"the submit view returned {response.status_code}, not a redirect, "
            f"so the form was not accepted"
        )

    page, snippet, french = ctx.submit_page, ctx.submit_snippet, ctx.locales["fr"]

    for label, instance in (("page", page), ("snippet", snippet)):
        if _translation_source(instance) is None:
            raise RuntimeError(f"no TranslationSource was created for the {label}.")
        if _translation_to(instance, french) is None:
            raise RuntimeError(f"the {label} was not translated into French.")
        if instance.get_translation_or_none(french) is None:
            raise RuntimeError(f"the {label} has no French target.")

    target = page.get_translation(french)
    expected = reverse("wagtailadmin_pages:edit", args=[target.id])
    if response.url != expected:
        raise RuntimeError(
            f"the redirect went to {response.url}, not to the editor of the "
            f"page it created ({expected})"
        )


SUBMIT_PAGE_POST = Flow(
    name="submit_page_post",
    group="creation",
    why=(
        "Creating a translation from the admin: the entry point an editor uses "
        "to put a page into another locale for the first time."
    ),
    entrypoint="SubmitPageTranslationView.post/form_valid",
    covers=(
        "TranslationCreator.create_translations",
        "TranslationSource.get_or_create_from_instance",
        "TranslationSource.refresh_segments",
        "Translation.save_target",
        "related snippet translation",
    ),
    setup=_submit_page_setup,
    run=_submit_page_run,
    verify=_submit_page_verify,
)


# ---------------------------------------------------------------------------
# edit_translation_get
# ---------------------------------------------------------------------------

# The container the translation editor renders its payload into. Wagtail's
# ordinary page editor also uses data-props, so that attribute alone would not
# prove which editor was served.
EDITOR_MARKER = 'class="js-translation-editor" data-props="'


def _editor_run(ctx, size):
    """GET the translation editor, and return the response unexamined.

    Reached through Wagtail's own page-edit URL, not a wagtail_localize one:
    `before_edit_page` finds the enabled Translation and hands off to
    `edit_translation`. That is the only way in.
    """
    from django.urls import reverse

    page_id = ctx.small_target_page_id if size == "small" else ctx.large_target_page_id
    return ctx.client.get(reverse("wagtailadmin_pages:edit", args=[page_id]))


def _editor_verify(ctx, size, response):
    """Check the editor really rendered, then count what it rendered.

    Runs outside the measured region, so parsing costs nothing the numbers see.
    Counts from the response body rather than response.context, which is None
    without the test runner's instrumentation.
    """
    import html
    import json
    import re

    if response.status_code != 200:
        raise RuntimeError(
            f"the editor returned {response.status_code}, not 200 — the flow "
            f"did not render the translation editor"
        )

    body = response.content.decode()
    if EDITOR_MARKER not in body:
        raise RuntimeError(
            "the response does not carry the translation editor's container, "
            "so the editor did not render — Wagtail's ordinary page editor was "
            "probably served instead, and the measurement is of the wrong view"
        )

    match = re.search(re.escape(EDITOR_MARKER) + r"([^\"]+)", body)
    props = json.loads(html.unescape(match.group(1)))
    return len(props["segments"])


EDIT_TRANSLATION_GET = Flow(
    name="edit_translation_get",
    group="editing",
    why=(
        "Rendering the translation editor: the view a translator works in, and "
        "the one whose cost grows with the number of segments on the page."
    ),
    entrypoint="before_edit_page -> edit_translation.edit_translation",
    covers=(
        "before_edit_page hook dispatch",
        "edit_translation view",
        "TabHelper / get_segment_location_info",
        "segment serialisation",
    ),
    workload_unit="rendered_segments",
    scale_points=(
        ScalePoint(
            label="small",
            why="An ordinary page, which gives the fixed cost of the view.",
            expected_workload=2,
        ),
        ScalePoint(
            label="large",
            why=(
                "The StreamField-heavy page, which makes the per-segment cost "
                "visible instead of hiding it inside the fixed cost."
            ),
            expected_workload=42,
        ),
    ),
    run=_editor_run,
    verify=_editor_verify,
)


# Creation before editing: a page is submitted before it is translated.
CATALOG = (SUBMIT_PAGE_POST, EDIT_TRANSLATION_GET)

BY_NAME = {flow.name: flow for flow in CATALOG}


def executions():
    """Every (flow, size) pair the catalog expands to."""
    return tuple((flow, size) for flow in CATALOG for size in flow.sizes())
