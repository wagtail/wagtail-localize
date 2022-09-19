import json

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.admin import messages
from wagtail.admin.views.pages.utils import get_valid_next_url_from_request
from wagtail.core.models import (
    Page,
    PageLogEntry,
    TranslatableMixin,
    _copy_m2m_relations,
)
from wagtail.core.signals import page_published

from wagtail_localize.models import Translation, TranslationSource


def convert_to_alias(request, page_id):
    page = get_object_or_404(Page, id=page_id, alias_of_id__isnull=True)
    if not page.permissions_for_user(request.user).can_edit():
        raise PermissionDenied

    try:
        translation_source = TranslationSource.objects.get(
            object_id=page.translation_key,
            specific_content_type=page.content_type_id,
            translations__target_locale=page.locale_id,
        )

        source_page = translation_source.get_source_instance()
    except (Page.DoesNotExist, TranslationSource.DoesNotExist):
        raise Http404

    # prevent self-aliasing
    if source_page.id == page_id:
        raise Http404

    page_to_alias = page.specific

    with transaction.atomic():
        next_url = get_valid_next_url_from_request(request)

        if request.method == "POST":
            # Sync with source page
            sync_alias(
                source_page, page_to_alias, revision=source_page.get_latest_revision()
            )

            # mark the page as an alias
            page_to_alias.alias_of_id = source_page.id
            page_to_alias.save(update_fields=["alias_of_id"], clean=False)

            # note, this logs the page title from before the sync
            page_title = page_to_alias.get_admin_display_title()
            PageLogEntry.objects.log_action(
                instance=page_to_alias,
                revision=page_to_alias.get_latest_revision(),
                action="wagtail_localize.convert_to_alias",
                user=request.user,
                data={
                    "page": {
                        "id": page_to_alias.id,
                        "title": page_title,
                    },
                    "source": {
                        "id": source_page.id,
                        "title": source_page.get_admin_display_title(),
                    },
                },
            )

            # Now clean up the old translation.
            # We are deleting rather than disabling old translations as we've just gone
            # back to an alias page, which by definition doesn't hold its own content
            try:
                translation = Translation.objects.get(
                    source=translation_source, target_locale=page_to_alias.locale_id
                )
                translation.delete()
            except Translation.DoesNotExist:
                pass

            messages.success(
                request,
                _("Page '{}' has been converted into an alias.").format(page_title),
            )

            if next_url:
                return redirect(next_url)
            return redirect("wagtailadmin_pages:edit", page_to_alias.id)

    return TemplateResponse(
        request,
        "wagtail_localize/admin/confirm_convert_to_alias.html",
        {
            "page": page_to_alias,
            "source_page": source_page,
            "next": next_url,
        },
    )


def sync_alias(source_page, alias_page, revision=None, _content_json=None):
    """
    Updates the page converted to an alias to be up-to-date with the source page.
    It will also update all aliases that follow this page with the latest content from this page.
    Note: this is a modified version of Page.update_aliases() for a single alias
    """
    source_page = source_page.specific

    # Only compute this if necessary since it's quite a heavy operation
    if _content_json is None:
        _content_json = source_page.to_json()

    if WAGTAIL_VERSION >= (3, 0):
        # see https://github.com/wagtail/wagtail/pull/8024
        _content_json = json.loads(_content_json)

    # FIXME: update when core adds better mechanism for the exclusions
    exclude_fields = [
        "id",
        "path",
        "depth",
        "numchild",
        "url_path",
        "path",
        "index_entries",
        "postgres_index_entries",
    ]

    # Copy field content
    alias_updated = alias_page.with_content_json(_content_json)

    # Mirror the publishing status of the status page
    alias_updated.live = source_page.live
    alias_updated.has_unpublished_changes = False

    # Copy child relations
    child_object_map = source_page.copy_all_child_relations(
        target=alias_updated, exclude=exclude_fields
    )

    # Process child objects
    if child_object_map:

        def process_child_object(child_object):
            if isinstance(child_object, TranslatableMixin):
                # Child object's locale must always match the page
                child_object.locale = alias_updated.locale

        for (_rel, previous_id), child_objects in child_object_map.items():
            if previous_id is None:
                for child_object in child_objects:
                    process_child_object(child_object)
            else:
                process_child_object(child_objects)

    # Copy M2M relations
    _copy_m2m_relations(source_page, alias_updated, exclude_fields=exclude_fields)

    # Don't change the aliases slug
    # Aliases can have their own slugs so they can be siblings of the original
    alias_updated.slug = alias_page.slug
    alias_updated.set_url_path(alias_updated.get_parent())

    # Technically, aliases don't have revisions, and in Page.update_aliases() fields that
    # would normally be updated by save_revision get updated. Let's mirror that.
    alias_updated.draft_title = alias_updated.title
    alias_updated.latest_revision_created_at = source_page.latest_revision_created_at

    alias_updated.save(clean=False)

    # question: should we sent the published alias?
    if alias_updated.live and not alias_page.live:
        page_published.send(
            sender=alias_updated.specific_class,
            instance=alias_updated,
            revision=revision,
            alias=True,
        )

    # Update any aliases of that alias
    if WAGTAIL_VERSION >= (3, 0):
        alias_page.update_aliases(revision=revision, _content=_content_json)
    else:
        alias_page.update_aliases(revision=revision, _content_json=_content_json)
