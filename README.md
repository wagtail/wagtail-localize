# Wagtail localize

<!--content-start-->

[![Version](https://img.shields.io/pypi/v/wagtail-localize.svg?style=flat)](https://pypi.python.org/pypi/wagtail-localize/)
[![License](https://img.shields.io/badge/license-BSD-blue.svg?style=flat)](https://opensource.org/licenses/BSD-3-Clause)
[![codecov](https://img.shields.io/codecov/c/github/wagtail/wagtail-localize?style=flat)](https://codecov.io/gh/wagtail/wagtail-localize)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/wagtail/wagtail-localize.svg?logo=lgtm&logoWidth=18&style=flat)](https://lgtm.com/projects/g/wagtail/wagtail-localize/context:python)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat)](https://github.com/pre-commit/pre-commit)

Wagtail Localize is a translation plugin for the [Wagtail CMS](https://wagtail.org). It allows pages or snippets to be translated within Wagtail's admin interface. It also provides integrations with external translations services such as [Pontoon](https://pontoon.mozilla.org/) or [DeepL](https://www.deepl.com/), and importing/exporting translations with PO files.

[Documentation](https://www.wagtail-localize.org)
[Changelog](https://github.com/wagtail/wagtail-localize/blob/main/CHANGELOG.md)

## Requirements

Wagtail Localize requires the following:

- Python (3.7, 3.8, 3.9, 3.10, 3.11)
- Django (3.2, 4.0, 4.1)
- Wagtail (2.15, 2.16, 3.0, 4.0, 4.1) with [internationalisation enabled](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html#configuration)

## Installation

Install using `pip`:

```shell
pip install wagtail-localize
```

Add `wagtail_localize` and `wagtail_localize.locales` to your `INSTALLED_APPS` setting:

```python
INSTALLED_APPS = [
    # ...
    "wagtail_localize",
    "wagtail_localize.locales",  # This replaces "wagtail.locales"
    # ...
]
```

## Contributing

All contributions are welcome!

### Install

To make changes to this project, first clone this repository:

```sh
git clone git@github.com:wagtail/wagtail-localize.git
cd wagtail-localize
```

With your preferred virtualenv activated, install testing dependencies:

#### Using pip

```sh
pip install pip>=21.3
pip install -e .[testing] -U
```

#### Using flit

```sh
pip install "flit>=3.8.0"
flit install
```

### pre-commit

Note that this project uses [pre-commit](https://github.com/pre-commit/pre-commit). To set up locally:

```shell
# if you don't have it yet, globally
$ pip install pre-commit
# go to the project directory
$ cd wagtail-localize
# initialize pre-commit
$ pre-commit install

# Optional, run all checks once for this, then the checks will run only on the changed files
$ pre-commit run --all-files
```

### How to run tests

Now you can run tests as shown below:

```sh
tox
```

or, you can run them for a specific environment `tox -e python3.8-django3.2-wagtail2.15` or specific test
`tox -e python3.9-django3.2-wagtail2.15-sqlite wagtail_localize.tests.test_edit_translation.TestGetEditTranslationView`

To run the test app interactively, use `tox -e interactive`, visit `http://127.0.0.1:8020/admin/` and log in with `admin`/`changeme`.

## Support

For support, please use [GitHub Discussions](https://github.com/wagtail/wagtail-localize/discussions) or ask a question on the `#multi-language` channel on [Wagtail's Slack instance](`https://wagtail.org/slack/`).

## Thanks

Many thanks to all of our supporters, contributors, and early adopters who helped with the initial release. In particular, to The Mozilla Foundation and Torchbox who sponsored the majority of the initial development and Wagtail core's internationalisation support.

<!--content-end-->
