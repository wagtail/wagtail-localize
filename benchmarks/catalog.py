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
# Page translations pre-created so the report view renders several rows.
REPORT_PAGE_TRANSLATIONS = 5
# StreamField blocks loaded onto the dedicated heavy page, so the flows that
# scale with segment count fan out over many segments instead of the handful an
# ordinary page carries.
REFRESH_SEGMENT_BLOCKS = 40
# How many segments the per-segment save flow writes at each size.
STRING_SAVES_SMALL = 5
STRING_SAVES_LARGE = REFRESH_SEGMENT_BLOCKS
# The page-submission flow keeps two distinct related snippets at both sizes
# and changes only how many times they are referenced. That separates repeated
# related-object work from the fixed cost of translating another distinct
# object.
SUBMIT_RELATED_REFERENCES = {
    "small": 2,
    "large": REFRESH_SEGMENT_BLOCKS,
}


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
                  [5:10]     tree filler; named by no flow, but counted by
                             core_page_index and walked by the subtree flow
                  [10]       heavy StreamField page, shared by every `large`
                  [11]       submit_page, left untranslated
        snippets: [0]        existing_snippet
                  [1]        extra report-only translation
                  [2]        submit_related_snippets, with [3]
                  [3]        submit_snippet, also in submit_related_snippets
    """
    from benchmarks.seed import build_snippet_pool, build_tree, ensure_locales

    locales = ensure_locales()
    snippets = build_snippet_pool(SNIPPETS, locales["en"])
    home, pages = build_tree(PAGES, locales["en"], snippets)
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
        # Subtree roots. Leaf pages have no children, so the flows that walk a
        # subtree need the home page or one of its categories.
        subtree_root_large=home,
        subtree_root_small=home.get_children().first(),
        submit_page=pages[-1],
        submit_snippet=snippets[-1],
        # Both are untouched by prepare(): the submit-page flow must create
        # their sources and French targets inside its measured POST. Keeping
        # this set fixed is what makes 2 vs 40 references a clean scale.
        submit_related_snippets=(snippets[-2], snippets[-1]),
    )


# ---------------------------------------------------------------------------
# Translation state, named per object rather than counted
#
# prepare() creates several translations, so every check has to identify the
# object, its own locale and the target locale. A count would pass whatever the
# flow did.
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
    """Build the related-reference workload and freeze its starting state.

    Both sizes reference the same two snippets. Only repetitions change, so
    the query difference belongs to the related-object loops rather than to
    translating more distinct dependencies. Publishing the workload belongs
    in setup: the measured operation is submitting that stored page, not
    editing it.
    """
    expected = SUBMIT_RELATED_REFERENCES.get(size)
    if expected is None:
        raise RuntimeError(f"submit_page_post has no size {size!r}.")

    page = ctx.submit_page
    snippets = ctx.submit_related_snippets
    french = ctx.locales["fr"]

    if page.test_snippet_id != snippets[-1].pk:
        raise RuntimeError(
            f"submit_page references snippet {page.test_snippet_id}, not "
            f"submit_snippet ({snippets[-1].pk})."
        )

    # The direct FK is one reference; StreamField supplies the rest. Start the
    # alternating sequence with the other snippet so small contains both.
    page.test_streamfield = [
        ("test_snippetchooserblock", snippets[number % len(snippets)])
        for number in range(expected - 1)
    ]
    page.save_revision().publish()
    page.refresh_from_db()

    stream_references = [
        block.value
        for block in page.test_streamfield
        if block.block_type == "test_snippetchooserblock"
    ]
    references = [page.test_snippet, *stream_references]
    if len(references) != expected:
        raise RuntimeError(
            f"the {size} page holds {len(references)} related references, not "
            f"the {expected} this scale measures."
        )
    expected_keys = {snippet.translation_key for snippet in snippets}
    actual_keys = {snippet.translation_key for snippet in references}
    if actual_keys != expected_keys:
        raise RuntimeError(
            f"the {size} page references objects {actual_keys}, not the fixed "
            f"two-object pool {expected_keys}."
        )

    for label, instance in (
        ("page", page),
        *(
            (f"related snippet {number}", snippet)
            for number, snippet in enumerate(snippets)
        ),
    ):
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
    """Check every source reference became the corresponding French one.

    Queries name the object and locale rather than counting rows: prepare()
    creates other translations, so a global count would pass whatever this POST
    did. The returned workload is the source's related segment count, while the
    target checks prevent a faster run that simply stopped ingesting them.
    """
    from collections import Counter

    from django.urls import reverse

    if response.status_code != 302:
        raise RuntimeError(
            f"the submit view returned {response.status_code}, not a redirect, "
            f"so the form was not accepted"
        )

    page = ctx.submit_page
    snippets = ctx.submit_related_snippets
    french = ctx.locales["fr"]

    for label, instance in (
        ("page", page),
        *(
            (f"related snippet {number}", snippet)
            for number, snippet in enumerate(snippets)
        ),
    ):
        if _translation_source(instance) is None:
            raise RuntimeError(f"no TranslationSource was created for the {label}.")
        if _translation_to(instance, french) is None:
            raise RuntimeError(f"the {label} was not translated into French.")
        if instance.get_translation_or_none(french) is None:
            raise RuntimeError(f"the {label} has no French target.")

    source = _translation_source(page)
    related_segments = list(
        source.relatedobjectsegment_set.select_related("object").order_by("order", "id")
    )
    expected = SUBMIT_RELATED_REFERENCES[size]
    if len(related_segments) != expected:
        raise RuntimeError(
            f"the submitted source holds {len(related_segments)} related "
            f"segments, not the {expected} declared by {size}."
        )
    source_stream_references = [
        block.value
        for block in page.test_streamfield
        if block.block_type == "test_snippetchooserblock"
    ]
    source_references = [page.test_snippet, *source_stream_references]
    source_reference_keys = [snippet.translation_key for snippet in source_references]
    segment_keys = [segment.object.translation_key for segment in related_segments]
    if Counter(segment_keys) != Counter(source_reference_keys):
        raise RuntimeError(
            "the source's related segments do not preserve its references: "
            f"{segment_keys} versus {source_reference_keys}."
        )

    target = page.get_translation(french).specific
    if not target.live or target.alias_of_id:
        raise RuntimeError(
            "the French page was not published as a real translated page."
        )

    stream_references = [
        block.value
        for block in target.test_streamfield
        if block.block_type == "test_snippetchooserblock"
    ]
    target_references = [target.test_snippet, *stream_references]
    if len(target_references) != expected:
        raise RuntimeError(
            f"the French target holds {len(target_references)} related "
            f"references, not the source's {expected}."
        )
    if any(snippet.locale_id != french.id for snippet in target_references):
        raise RuntimeError("the French page still references a source-locale snippet.")
    target_reference_keys = [snippet.translation_key for snippet in target_references]
    if target_reference_keys != source_reference_keys:
        raise RuntimeError(
            "the French page changed the order or identity of its related "
            f"references: {target_reference_keys} versus {source_reference_keys}."
        )

    expected = reverse("wagtailadmin_pages:edit", args=[target.id])
    if response.url != expected:
        raise RuntimeError(
            f"the redirect went to {response.url}, not to the editor of the "
            f"page it created ({expected})"
        )

    return len(related_segments)


# ---------------------------------------------------------------------------
# submit_page_post
# ---------------------------------------------------------------------------


SUBMIT_PAGE_POST = Flow(
    name="submit_page_post",
    group="creation",
    why=(
        "Creating a translation from the admin: the entry point an editor uses "
        "to put a page into another locale for the first time. Repeating a "
        "fixed set of related snippets exposes both the creation fan-out and "
        "the related-object checks while saving the target."
    ),
    entrypoint="SubmitPageTranslationView.post/form_valid",
    covers=(
        "TranslationCreator.create_translations",
        "TranslationSource.get_or_create_from_instance",
        "TranslationSource.refresh_segments",
        "Translation.save_target",
        "related snippet fan-out and target ingestion",
    ),
    workload_unit="related_object_segments",
    scale_points=(
        ScalePoint(
            label="small",
            why="Two distinct snippets, each referenced once.",
            expected_workload=SUBMIT_RELATED_REFERENCES["small"],
        ),
        ScalePoint(
            label="large",
            why=(
                "The same two snippets repeated forty times, so the difference "
                "is repeated related-object work rather than more dependencies."
            ),
            expected_workload=SUBMIT_RELATED_REFERENCES["large"],
        ),
    ),
    setup=_submit_page_setup,
    run=_submit_page_run,
    verify=_submit_page_verify,
)


# ---------------------------------------------------------------------------
# submit_snippet_post
# ---------------------------------------------------------------------------


def _snippet_url_parts(snippet):
    """The app label, model name and pk the snippet admin URLs are built from."""
    meta = type(snippet)._meta
    return meta.app_label, meta.model_name, snippet.pk


def _submit_snippet_setup(ctx, size):
    """Assert the snippet starts untranslated, so the POST creates rather than
    reconciles."""
    if size is not None:
        raise RuntimeError(f"submit_snippet_post takes no size; got {size!r}.")

    snippet, french = ctx.submit_snippet, ctx.locales["fr"]
    if _translation_source(snippet) is not None:
        raise RuntimeError("submit_snippet already has a TranslationSource.")
    if _translation_to(snippet, french) is not None:
        raise RuntimeError("submit_snippet is already translated into French.")
    if snippet.get_translation_or_none(french) is not None:
        raise RuntimeError("submit_snippet already has a French target.")


def _submit_snippet_run(ctx, size):
    """POST the snippet submit form, and return the response unexamined."""
    from django.urls import reverse

    app_label, model_name, pk = _snippet_url_parts(ctx.submit_snippet)
    return ctx.client.post(
        reverse(
            "wagtail_localize:submit_snippet_translation",
            args=[app_label, model_name, pk],
        ),
        {"locales": [ctx.locales["fr"].id]},
    )


def _submit_snippet_verify(ctx, size, response):
    """Check the snippet was translated and the redirect names that translation."""
    from django.contrib.admin.utils import quote
    from django.urls import reverse

    if response.status_code != 302:
        raise RuntimeError(
            f"the submit view returned {response.status_code}, not a redirect"
        )

    snippet, french = ctx.submit_snippet, ctx.locales["fr"]
    if _translation_source(snippet) is None:
        raise RuntimeError("no TranslationSource was created for the snippet.")
    if _translation_to(snippet, french) is None:
        raise RuntimeError("the snippet was not translated into French.")

    target = snippet.get_translation_or_none(french)
    if target is None:
        raise RuntimeError("the snippet has no French target.")
    if target.field != snippet.field:
        raise RuntimeError(
            f"the French target carries {target.field!r}, not the source's "
            f"{snippet.field!r}: the content was not copied across."
        )

    app_label, model_name, _pk = _snippet_url_parts(snippet)
    expected = reverse(
        f"wagtailsnippets_{app_label}_{model_name}:edit", args=[quote(target.pk)]
    )
    if response.url != expected:
        raise RuntimeError(
            f"the redirect went to {response.url}, not to the editor of the "
            f"translation it created ({expected})"
        )


SUBMIT_SNIPPET_POST = Flow(
    name="submit_snippet_post",
    group="creation",
    why=(
        "Creating a snippet translation from the admin: the same translation "
        "core reached from a different entry point than pages."
    ),
    entrypoint="SubmitSnippetTranslationView.post/form_valid",
    covers=(
        "TranslationCreator.create_translations",
        "TranslationSource.get_or_create_from_instance",
        "Translation.save_target",
    ),
    setup=_submit_snippet_setup,
    run=_submit_snippet_run,
    verify=_submit_snippet_verify,
)


# ---------------------------------------------------------------------------
# update_translations_get
# ---------------------------------------------------------------------------


def _enabled_translations(source):
    """The source's enabled translations, ordered so comparisons are stable."""
    return list(source.translations.filter(enabled=True).order_by("target_locale_id"))


def _target_state(translations):
    """Enough of each target's state to notice any write to it.

    latest_revision_id and live catch a new revision and a change of live
    state, but not republishing when the target was already live: Wagtail then
    moves live_revision_id and last_published_at while those two stay put.
    """
    state = {}
    for translation in translations:
        target = translation.get_target_instance()
        state[translation.id] = (
            target.pk,
            target.live,
            target.latest_revision_id,
            target.live_revision_id,
            target.last_published_at,
        )
    return state


def _update_translations_get_setup(ctx, size):
    """Put the source at the number of enabled translations this size measures.

    The view calls get_target_instance() twice per translation and that method
    does not cache, so the cost tracks the count. `large` creates the second
    translation here, outside the measured region, rather than in prepare():
    it belongs to this size, and building it globally would change `small`.
    """
    source = ctx.existing_page_source
    spanish = ctx.locales["es"]

    if _translation_to(ctx.existing_page, spanish) is not None:
        raise RuntimeError("the source already has a Spanish translation.")
    if size == "large":
        _create_translation(ctx.existing_page, spanish, user=ctx.user)

    expected = 1 if size == "small" else 2
    enabled = _enabled_translations(source)
    if len(enabled) != expected:
        raise RuntimeError(
            f"the source has {len(enabled)} enabled translations, not the "
            f"{expected} this size measures."
        )

    # Snapshot for the no-write check: counting revisions on the source would
    # not notice a target being revised or republished. Verification state, not
    # workload.
    ctx.translations_before = {translation.id for translation in enabled}
    ctx.targets_before = _target_state(enabled)


def _update_translations_get_run(ctx, size):
    """GET the update-translations screen, and return the response unexamined."""
    from django.urls import reverse

    return ctx.client.get(
        reverse(
            "wagtail_localize:update_translations",
            args=[ctx.existing_page_source.id],
        )
    )


def _update_translations_get_verify(ctx, size, response):
    """Check every enabled translation is listed, and that nothing was written."""
    from django.urls import reverse

    if response.status_code != 200:
        raise RuntimeError(
            f"the update screen returned {response.status_code}, not 200"
        )

    body = response.content.decode()
    enabled = _enabled_translations(ctx.existing_page_source)

    # The screen links to each target's editor, which is what proves it listed
    # the translation rather than merely rendering the page.
    for translation in enabled:
        target = translation.get_target_instance()
        if reverse("wagtailadmin_pages:edit", args=[target.id]) not in body:
            raise RuntimeError(
                f"the screen does not link to the {translation.target_locale} "
                f"target, so it did not list that translation."
            )

    if {translation.id for translation in enabled} != ctx.translations_before:
        raise RuntimeError("opening the screen changed the set of translations.")

    after = _target_state(enabled)
    if after != ctx.targets_before:
        raise RuntimeError(
            f"opening the screen changed a target: {ctx.targets_before} became "
            f"{after}. A GET must not revise or publish anything."
        )

    return len(enabled)


UPDATE_TRANSLATIONS_GET = Flow(
    name="update_translations_get",
    group="updating",
    why=(
        "Opening the screen that lists a source's existing translations, the "
        "step before deciding whether to republish them."
    ),
    entrypoint="UpdateTranslationsView.get/get_context_data",
    covers=(
        "enabled translation listing",
        "Translation.get_target_instance per translation",
        "target edit URL construction",
    ),
    workload_unit="enabled_translations",
    scale_points=(
        ScalePoint(
            label="small",
            why="One translation: the fixed cost of the screen.",
            expected_workload=1,
        ),
        ScalePoint(
            label="large",
            why=(
                "Two translations, so the per-translation cost of resolving "
                "each target separates from the fixed cost."
            ),
            expected_workload=2,
        ),
    ),
    setup=_update_translations_get_setup,
    run=_update_translations_get_run,
    verify=_update_translations_get_verify,
)


# ---------------------------------------------------------------------------
# update_translations_post_publish
# ---------------------------------------------------------------------------

# Deterministic, so a failure names the value it expected rather than a
# timestamp nobody can predict.
UPDATE_MARKERS = {
    "small": "benchmark-update-small",
    "large": "benchmark-update-large",
}


def _update_source(size, ctx):
    """The page and source this size updates."""
    if size == "small":
        return ctx.existing_page, ctx.existing_page_source
    return ctx.heavy_page, ctx.heavy_page_source


def _update_translations_post_setup(ctx, size):
    """Make the source stale, so the POST has real reconciliation to do.

    The marker goes in a synchronized field: those are copied to the target
    verbatim by copy_synchronised_fields, so it arrives without needing a
    translation. A translatable field would become a segment and stay in the
    source language.
    """
    page, source = _update_source(size, ctx)
    marker = UPDATE_MARKERS[size]

    # The POST republishes every enabled translation, so its cost tracks that
    # number too. The declared workload is segments, so the count is pinned
    # here rather than left to whatever the fixture happens to hold.
    enabled = _enabled_translations(source)
    if len(enabled) != 1:
        raise RuntimeError(
            f"the source has {len(enabled)} enabled translations; this flow "
            f"measures updating exactly one."
        )
    if enabled[0].target_locale_id != ctx.locales["fr"].id:
        raise RuntimeError(
            f"the enabled translation targets {enabled[0].target_locale}, not French."
        )

    target = page.get_translation_or_none(ctx.locales["fr"])
    if target is None:
        raise RuntimeError("the page has no French target to republish.")
    if target.test_synchronized_charfield == marker:
        raise RuntimeError("the target already carries the marker.")

    page.test_synchronized_charfield = marker
    page.save_revision().publish()


def _update_translations_post_run(ctx, size):
    """POST the update form with publish, and return the response unexamined."""
    from django.urls import reverse

    _page, source = _update_source(size, ctx)
    return ctx.client.post(
        reverse("wagtail_localize:update_translations", args=[source.id]),
        {"publish_translations": "on"},
    )


def _update_translations_post_verify(ctx, size, response):
    """Check the source was refreshed and the marker reached the live target."""
    if response.status_code != 302:
        raise RuntimeError(
            f"the update view returned {response.status_code}, not a redirect"
        )

    page, source = _update_source(size, ctx)
    marker = UPDATE_MARKERS[size]

    target = page.get_translation_or_none(ctx.locales["fr"])
    if target is None:
        raise RuntimeError("the French target disappeared.")
    if target.test_synchronized_charfield != marker:
        raise RuntimeError(
            f"the target carries {target.test_synchronized_charfield!r}, not "
            f"{marker!r}: the source change was not copied across."
        )
    if not target.live:
        raise RuntimeError("the target was not published.")

    source.refresh_from_db()
    return source.stringsegment_set.count()


UPDATE_TRANSLATIONS_POST_PUBLISH = Flow(
    name="update_translations_post_publish",
    group="updating",
    why=(
        "Pushing a change made to the original out to its translations and "
        "publishing them, the update half of the translation cycle."
    ),
    entrypoint="UpdateTranslationsView.form_valid",
    covers=(
        "TranslationSource.update_from_db",
        "TranslationSource.refresh_segments",
        "Translation.save_target",
        "copy_synchronised_fields",
    ),
    workload_unit="string_segments",
    scale_points=(
        ScalePoint(
            label="small",
            why="An ordinary page: the fixed cost of refreshing and publishing.",
            expected_workload=1,
        ),
        ScalePoint(
            label="large",
            why=(
                "The StreamField-heavy page, where re-extracting segments "
                "dominates the fixed cost."
            ),
            expected_workload=41,
        ),
    ),
    setup=_update_translations_post_setup,
    run=_update_translations_post_run,
    verify=_update_translations_post_verify,
)


# ---------------------------------------------------------------------------
# translate_page_subtree
# ---------------------------------------------------------------------------


def _subtree_root(ctx, size):
    return ctx.subtree_root_small if size == "small" else ctx.subtree_root_large


def _french_state(page, french):
    """Classify a page's French state from all three facts at once.

    The target alone does not say what Localize knows about the page, so the
    TranslationSource and the Translation are read with it. Only three
    combinations are states the subtree flow understands; anything else means
    the fixture is not what the scenario assumes, and is raised rather than
    quietly counted as one of them.
    """
    specific = page.specific
    target = specific.get_translation_or_none(french)
    source = _translation_source(specific) is not None
    translation = _translation_to(specific, french) is not None

    if target is not None and not target.alias_of_id and source and translation:
        return "translated"
    if target is not None and target.alias_of_id and not source and not translation:
        return "alias"
    if target is None and not source and not translation:
        return "untranslated"

    raise RuntimeError(
        f"{page.slug} is in no state this flow recognises: "
        f"target={'alias' if target is not None and target.alias_of_id else target is not None}, "
        f"source={source}, translation={translation}."
    )


# The mix prepare() leaves under each root. Frozen because the cost of the walk
# depends on it: a subtree of already-translated pages is not the same work as
# one of untranslated pages, and a run against a different mix would measure
# something else under the same name.
SUBTREE_MIX = {
    "small": {"translated": 2, "alias": 0, "untranslated": 1},
    "large": {"translated": 6, "alias": 4, "untranslated": 6},
}


def _submit_subtree_setup(ctx, size):
    """Freeze the scenario: the root, its size, and the mix underneath it."""
    root, french = _subtree_root(ctx, size), ctx.locales["fr"]

    descendants = list(root.get_descendants())
    expected = sum(SUBTREE_MIX[size].values())
    if len(descendants) != expected:
        raise RuntimeError(
            f"the {size} root has {len(descendants)} descendants, not the "
            f"{expected} this size measures."
        )

    if _translation_source(root.specific) is not None:
        raise RuntimeError("the root is already a translation source.")
    if _french_state(root, french) != "alias":
        raise RuntimeError(
            "the root's French counterpart is not an alias, so this run would "
            "not measure converting one into a real translation."
        )

    observed = {"translated": 0, "alias": 0, "untranslated": 0}
    for page in descendants:
        observed[_french_state(page, french)] += 1
    if observed != SUBTREE_MIX[size]:
        raise RuntimeError(
            f"the {size} subtree holds {observed}, not {SUBTREE_MIX[size]}. "
            f"The cost of the walk depends on this mix."
        )


def _submit_subtree_run(ctx, size):
    """POST the submit form with the subtree included.

    There is no URL of its own: translate_page_subtree is enqueued by the
    submit view, and the harness settings leave the job backend on
    ImmediateBackend, so the walk runs inside this request.
    """
    from django.urls import reverse

    root = _subtree_root(ctx, size)
    return ctx.client.post(
        reverse("wagtail_localize:submit_page_translation", args=[root.id]),
        {"locales": [ctx.locales["fr"].id], "include_subtree": "on"},
    )


def _submit_subtree_verify(ctx, size, response):
    """Check the root and every descendant came out really translated."""
    from django.urls import reverse

    if response.status_code != 302:
        raise RuntimeError(
            f"the submit view returned {response.status_code}, not a redirect"
        )

    root, french = _subtree_root(ctx, size), ctx.locales["fr"]

    for label, page in [
        ("root", root),
        *[("descendant", p) for p in root.get_descendants()],
    ]:
        specific = page.specific
        if _translation_source(specific) is None:
            raise RuntimeError(f"a {label} has no TranslationSource: {page.slug}")
        if _translation_to(specific, french) is None:
            raise RuntimeError(f"a {label} was not translated: {page.slug}")
        target = specific.get_translation_or_none(french)
        if target is None:
            raise RuntimeError(f"a {label} has no French target: {page.slug}")
        if target.alias_of_id:
            raise RuntimeError(
                f"a {label} is still an alias rather than a real translation: "
                f"{page.slug}"
            )
        if not target.live:
            raise RuntimeError(f"a {label}'s target is not published: {page.slug}")

    translated_root = root.specific.get_translation(french)
    expected = reverse("wagtailadmin_pages:edit", args=[translated_root.id])
    if response.url != expected:
        raise RuntimeError(
            f"the redirect went to {response.url}, not to the editor of the "
            f"translated root ({expected})"
        )

    # The root is fixed cost measured alongside the walk, so it is not counted.
    return root.get_descendants().count()


TRANSLATE_PAGE_SUBTREE = Flow(
    name="translate_page_subtree",
    group="creation",
    why=(
        "Translating a page together with everything under it: one click that "
        "walks a whole branch of the tree."
    ),
    entrypoint="SubmitPageTranslationView.form_valid -> translate_page_subtree",
    covers=(
        "translate_object on the root",
        "translate_page_subtree recursive walk",
        "TranslationCreator.create_translations per descendant",
        "alias conversion into a real translation",
    ),
    workload_unit="pages_in_subtree",
    scale_points=(
        ScalePoint(
            label="small",
            why="A single category: three pages under one parent.",
            expected_workload=3,
        ),
        ScalePoint(
            label="large",
            why=(
                "The whole benchmark tree, where the walk crosses two levels "
                "and a mix of translated, aliased and untouched pages."
            ),
            expected_workload=16,
        ),
    ),
    setup=_submit_subtree_setup,
    run=_submit_subtree_run,
    verify=_submit_subtree_verify,
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


# ---------------------------------------------------------------------------
# core_refresh_segments
#
# A core probe rather than an admin flow: it calls one model method directly,
# because the question is about that method and nothing else.
# ---------------------------------------------------------------------------


def _refresh_source(ctx, size):
    return ctx.existing_page_source if size == "small" else ctx.heavy_page_source


def _refresh_segment_state(source):
    """Every segment row the source owns, per type, as ids in order.

    Ids rather than counts, because the postcondition is that reconciling an
    unchanged source leaves the rows alone: a count would pass a run that
    deleted a segment and created another one in its place. Local to this
    probe — the other flows check the objects they act on, not this shape.
    """
    from wagtail_localize.models import (
        OverridableSegment,
        RelatedObjectSegment,
        StringSegment,
        TemplateSegment,
    )

    return {
        model.__name__: list(
            model.objects.filter(source=source)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )
        for model in (
            StringSegment,
            TemplateSegment,
            RelatedObjectSegment,
            OverridableSegment,
        )
    }


def _core_refresh_setup(ctx, size):
    """Freeze the state the refresh is supposed to reconcile against.

    The source must already exist with its segments written: this probe
    measures re-extraction over a source that is already reconciled, which is
    the variant the characterization test covers. A first extraction is a
    different operation, and submit_page_post already measures it.
    """
    source = _refresh_source(ctx, size)
    if source is None or source.pk is None:
        raise RuntimeError(f"prepare() left no saved {size} source to refresh.")

    state = _refresh_segment_state(source)
    if not state["StringSegment"]:
        raise RuntimeError(
            f"the {size} source holds no string segments, so refreshing it "
            f"would measure a first extraction instead of a reconciliation."
        )
    ctx.core_refresh_state = state


def _core_refresh_run(ctx, size):
    """Reconcile the source's segments, and nothing else."""
    _refresh_source(ctx, size).refresh_segments()


def _core_refresh_verify(ctx, size, artifacts):
    """Check the reconciliation left every segment row where it was.

    Refreshing a source whose content has not changed has to be a no-op in the
    data: the same rows, in the same order, none deleted and none recreated.
    Returns the string segments the source holds, which is what the measured
    queries scale with.
    """
    before = ctx.core_refresh_state
    after = _refresh_segment_state(_refresh_source(ctx, size))

    for name, ids in before.items():
        if after[name] != ids:
            raise RuntimeError(
                f"reconciling an unchanged source changed its {name} rows: "
                f"{ids} before, {after[name]} after."
            )

    return len(after["StringSegment"])


CORE_REFRESH_SEGMENTS = Flow(
    name="core_refresh_segments",
    group="core",
    why=(
        "Re-extracting the segments of a source that already has them. It runs "
        "inside submit, update and subtree translation, where its cost arrives "
        "mixed with content extraction and target saving; called on its own it "
        "shows the per-segment persistence on its own."
    ),
    entrypoint="TranslationSource.refresh_segments",
    covers=(
        "TranslationSource.as_instance",
        "extract_segments over the stored content",
        "String, TranslationContext and StringSegment get_or_create per segment",
        "deletion of the segments the extraction no longer mentions",
    ),
    workload_unit="string_segments",
    scale_points=(
        ScalePoint(
            label="small",
            why="An ordinary page: one string segment, so the fixed cost dominates.",
            expected_workload=1,
        ),
        ScalePoint(
            label="large",
            why=(
                "The StreamField-heavy page, whose segments are the only "
                "difference from the small one, so the subtraction leaves the "
                "per-segment cost alone."
            ),
            expected_workload=41,
        ),
    ),
    setup=_core_refresh_setup,
    run=_core_refresh_run,
    verify=_core_refresh_verify,
)


# ---------------------------------------------------------------------------
# core_page_index
#
# The index reads the whole page table, so its scale cannot be chosen with a
# root: the large size adds pages to the site instead.
# ---------------------------------------------------------------------------

# Plain pages the large size adds so the two sizes differ by a known amount.
# Local to this probe: the shared fixture constants describe content the admin
# flows act on, and these pages exist only to be counted.
INDEX_FILLER_PAGES = 40


def _indexable_pages():
    """The pages PageIndex.from_database() walks: every page below the root
    that is not an alias."""
    from wagtail.models import Page

    return Page.objects.filter(alias_of__isnull=True, depth__gt=1)


def _index_entry(index, page):
    """The index entry built from `page`, or None.

    Matched on locale as well as translation key, because translated variants
    share a key and the index holds one entry per variant.
    """
    for entry in index.pages:
        if (
            entry.translation_key == page.translation_key
            and entry.source_locale.id == page.locale_id
        ):
            return entry
    return None


def _core_page_index_setup(ctx, size):
    """Bring the site to the size being measured, and freeze what verify needs.

    The large size creates its pages here, outside the measured region: the
    probe measures reading the page table, not writing to it.
    """
    from wagtail.models import Page

    from tests.testapp.models import TestPage

    if size == "large":
        # prepare() exports the English home as the large subtree root.
        home = ctx.subtree_root_large
        for number in range(INDEX_FILLER_PAGES):
            home.add_child(
                instance=TestPage(
                    title=f"Index filler {number}",
                    slug=f"bench-index-filler-{number}",
                    locale=ctx.locales["en"],
                )
            )

    expected = 24 if size == "small" else 24 + INDEX_FILLER_PAGES
    indexable = _indexable_pages().count()
    if indexable != expected:
        raise RuntimeError(
            f"the {size} size holds {indexable} indexable pages, not the "
            f"{expected} it measures. The index reads the whole page table, so "
            f"anything that creates or removes pages changes this number."
        )

    if not Page.objects.filter(alias_of__isnull=False).exists():
        raise RuntimeError(
            "the fixture holds no alias pages, so the index would never fill "
            "aliased_locales and the scenario would be a weaker one than named."
        )

    # Read here rather than in verify so the expectation comes from the fixture
    # and not from the index being checked against itself.
    ctx.core_index_parent_key = ctx.existing_page.get_parent().translation_key


def _core_page_index_run(ctx, size):
    """Build the index. This is the whole measured region."""
    from wagtail_localize.synctree import PageIndex

    return PageIndex.from_database()


def _core_page_index_verify(ctx, size, index):
    """Check the index describes the site it was built from.

    The three properties below are the ones 719447f stops computing per page
    and starts resolving from preloaded maps, so an arm that reduced the query
    count by losing information fails here rather than looking like a win.
    """
    indexable = _indexable_pages().count()
    if len(index.pages) != indexable:
        raise RuntimeError(
            f"the index holds {len(index.pages)} entries for {indexable} "
            f"indexable pages."
        )

    english, french = ctx.locales["en"], ctx.locales["fr"]

    entry = _index_entry(index, ctx.existing_page)
    if entry is None:
        raise RuntimeError("the index has no entry for the translated page.")
    if set(entry.locales) != {english.id, french.id}:
        raise RuntimeError(
            f"the translated page's entry lists locales {entry.locales}, not "
            f"the English and French ones it exists in."
        )
    if entry.parent_translation_key != ctx.core_index_parent_key:
        raise RuntimeError(
            f"the translated page's entry points at parent "
            f"{entry.parent_translation_key}, not at {ctx.core_index_parent_key}."
        )

    home_entry = _index_entry(index, ctx.subtree_root_large)
    if home_entry is None:
        raise RuntimeError("the index has no entry for the home page.")
    if french.id not in home_entry.aliased_locales:
        raise RuntimeError(
            f"the home entry lists aliased locales {home_entry.aliased_locales}, "
            f"without the French alias the fixture created."
        )

    return len(index.pages)


CORE_PAGE_INDEX = Flow(
    name="core_page_index",
    group="core",
    why=(
        "Building the page index synchronize_tree walks. Inside the full sync "
        "the index is a small part of a much larger copy operation, so on its "
        "own is the only place where a per-page cost in the index is visible "
        "at all."
    ),
    entrypoint="PageIndex.from_database",
    covers=(
        "PageIndex.from_database",
        "PageIndex.Entry.from_page_instance per indexed page",
        "the locales and aliased_locales lookups behind each entry",
        "the parent lookup behind each entry",
    ),
    workload_unit="indexed_pages",
    scale_points=(
        ScalePoint(
            label="small",
            why="The benchmark site as the fixture builds it.",
            expected_workload=24,
        ),
        ScalePoint(
            label="large",
            why=(
                "The same site with forty more pages under the home, which is "
                "the only difference between the two sizes, so the subtraction "
                "leaves the per-page cost alone."
            ),
            expected_workload=24 + INDEX_FILLER_PAGES,
        ),
    ),
    setup=_core_page_index_setup,
    run=_core_page_index_run,
    verify=_core_page_index_verify,
)


# Grouped by what a flow does, creation entrypoints before the editor, and the
# core probes last. Not a sequence: every execution runs against a fresh
# database, so no flow's result feeds the next.
CATALOG = (
    SUBMIT_PAGE_POST,
    SUBMIT_SNIPPET_POST,
    TRANSLATE_PAGE_SUBTREE,
    EDIT_TRANSLATION_GET,
    UPDATE_TRANSLATIONS_GET,
    UPDATE_TRANSLATIONS_POST_PUBLISH,
    CORE_REFRESH_SEGMENTS,
    CORE_PAGE_INDEX,
)

BY_NAME = {flow.name: flow for flow in CATALOG}


def executions():
    """Every (flow, size) pair the catalog expands to."""
    return tuple((flow, size) for flow in CATALOG for size in flow.sizes())
