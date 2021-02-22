---
template: templates/index.html
---

![Wagtail Localize](/_static/banner.png)

Wagtail Localize is a translation plugin for the [Wagtail CMS](https://github.com/wagtail/wagtail). It allows pages or snippets to be translated within Wagtail's admin interface. It also provides integrations with external translations services such as [Pontoon](https://pontoon.mozilla.org/) or [DeepL](https://www.deepl.com/), and importing/exporting translations with PO files.

## Requirements

Wagtail Localize requires the following:

 - Python (3.7, 3.8)
 - Django (2.11, 3.0, 3.1)
 - Wagtail (2.11, 2.12) with [internationalisation enabled](https://docs.wagtail.io/en/stable/advanced_topics/i18n.html#configuration)

## Installation

Install using ``pip``:

```shell
pip install wagtail-localize
```

Add ``wagtail_localize`` and ``wagtail_localize.locales`` to your ``INSTALLED_APPS`` setting:

```python
INSTALLED_APPS = [
    ...
    "wagtail_localize",
    "wagtail_localize.locales",  # This replaces "wagtail.locales"
    ...
]
```

## Support

For support, please use [GitHub Discussions](https://github.com/wagtail/wagtail-localize/discussions) or ask a question on the ``#multi-language`` channel on [Wagtail's Slack instance](https://wagtail.io/slack/).

## Thanks

Many thanks to all of our supporters, contributors, and early adopters who helped with the initial release. In particular, to The Mozilla Foundation and Torchbox who sponsored the majority of the initial development and Wagtail core's internationalisation support.
