# Installation guide

Before you start, follow Wagtail's [configuration guide](https://docs.wagtail.io/en/stable/advanced_topics/i18n.html#configuration)
to enable internationalisation in Wagtail and Django.

## Install the Python package

Firstly install ``wagtial-localize`` Python package.

If you are using ``pip``, use the following command:

```shell
pip install wagtail-localize
```

## Add to ``INSTALLED_APPS``

Now add ``wagtail_localize`` to your ``INSTALLED_APPS`` setting:

```python
INSTALLED_APPS = [
    ...
    "wagtail_localize",
    ...
]
```

## Enabling the "Sync from" field (optional)

Wagtail Localize has a feature that allows you to automatically synchronise language trees. This means that any new
pages created in a source language are automatically created as an alias in another language.

The locales that are synchronised from others can be managed through the Wagtail admin interface.

To enable this, replace the ``"wagtail.locales"`` entry in ``INSTALLED_APPS`` with ``"wagtail_localize.locales"``, this
will add a "Sync from" field to all locales that allows an administrator to choose a locale to synchronise content from.
