# Wagtail localize

<!--content-start-->

[![Version](https://img.shields.io/pypi/v/wagtail-localize.svg?style=flat)](https://pypi.python.org/pypi/wagtail-localize/)
[![License](https://img.shields.io/badge/license-BSD-blue.svg?style=flat)](https://opensource.org/licenses/BSD-3-Clause)
[![codecov](https://img.shields.io/codecov/c/github/wagtail/wagtail-localize?style=flat)](https://codecov.io/gh/wagtail/wagtail-localize)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/wagtail/wagtail-localize.svg?logo=lgtm&logoWidth=18&style=flat)](https://lgtm.com/projects/g/wagtail/wagtail-localize/context:python)

Wagtail Localize is a translation plugin for the [Wagtail CMS](https://wagtail.io). It allows pages or snippets to be translated within Wagtail's admin interface. It also provides integrations with external translations services such as [Pontoon](https://pontoon.mozilla.org/) or [DeepL](https://www.deepl.com/), and importing/exporting translations with PO files.

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

<!--content-end-->
