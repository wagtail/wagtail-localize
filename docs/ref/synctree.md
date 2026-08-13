# Synctree module

The synctree module implements the logic that keeps locale trees in sync.

## Page Status Control

When synchronizing content between locales, you can control how the page status (live/draft) is handled for the synced pages. This is controlled by the `sync_page_status` field on the `LocaleSynchronization` model.

### Available Options

- **Mirror source status** (`MIRROR`): The default behavior. Synced pages will have the same live/draft status as their source pages.
- **Draft (always unpublished)** (`DRAFT`): All synced pages will be created as drafts, regardless of the source page's status.

### When to Use Each Option

- **Use Mirror** when you want the synced content to immediately reflect the same publishing state as the source locale. This is useful when you have a well-established content workflow and want to maintain consistency.

- **Use Draft** when you want to review and configure other aspects of your site (like navigation menus, site settings, etc.) before making the synced content live. This prevents untranslated content from automatically going live.

### Configuration

The `sync_page_status` field can be set when creating or editing a locale synchronization in the Wagtail admin. This setting applies to:

1. Initial content tree synchronization when the sync is first created
2. Ongoing automatic synchronization of new pages created in the source locale

::: wagtail_localize.synctree
