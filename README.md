# Wagtail localize

<!--content-start-->

[![Version](https://img.shields.io/pypi/v/wagtail-localize.svg?style=flat)](https://pypi.python.org/pypi/wagtail-localize/)
[![License](https://img.shields.io/badge/license-BSD-blue.svg?style=flat)](https://opensource.org/licenses/BSD-3-Clause)
[![codecov](https://img.shields.io/codecov/c/github/wagtail/wagtail-localize?style=flat)](https://codecov.io/gh/wagtail/wagtail-localize)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/wagtail/wagtail-localize/main.svg)](https://results.pre-commit.ci/latest/github/wagtail/wagtail-localize/main)

Wagtail Localize is a translation plugin for the [Wagtail CMS](https://wagtail.org). It allows pages or snippets to be translated within Wagtail's admin interface. It also provides integrations with external translations services such as [Pontoon](https://pontoon.mozilla.org/) or [DeepL](https://www.deepl.com/), and importing/exporting translations with PO files.

[Documentation](https://wagtail-localize.org)
[Changelog](https://github.com/wagtail/wagtail-localize/blob/main/CHANGELOG.md)

## Join the Community at Wagtail Space!

We'll be at Wagtail Space US this year! The Call for Participation and Registration for both Wagtail Space 2024 events is open. We would love to have you give a talk, or just us as an attendee in June.

- [Wagtail Space NL](https://nl.wagtail.space/), Arnhem, The Netherlands. 2024-06-14
- [Wagtail Space US](https://us.wagtail.space/), Philadelphia, PA. 2024-06-20 to 2024-06-22

## Requirements

Wagtail Localize requires the following:

- Python (3.9, 3.10, 3.11, 3.12, 3.13)
- Django (4.2, 5.1, 5.2)
- Wagtail (5.2 - 7.0) with [internationalisation enabled](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html#configuration)
- [wagtail-modeladmin](https://pypi.org/project/wagtail-modeladmin/) if `using wagtail_localize.modeladmin` and Wagtail >= 5.2

## Installation

Before you start, follow Wagtail's [configuration guide](https://docs.wagtail.org/en/stable/advanced_topics/i18n.html#configuration)
to enable internationalisation in Wagtail and Django.

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

`wagtail-localize` loads additional assets for the editing interface. Run the `collectstatic` management command to collect all the required assets.

```shell
python manage.py collectstatic
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
pip install "pip>=21.3"
pip install -e '.[testing]' -U
```

#### Using flit

```sh
pip install "flit>=3.8.0"
flit install
```

### pre-commit

Note that this project uses [pre-commit](https://github.com/pre-commit/pre-commit). To set up locally:

```shell
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

or, you can run them for a specific environment `tox -e python3.13-django5.2-wagtail7.0` or specific test
`tox -e python3.13-django5.2-wagtail7.0-sqlite -- wagtail_localize.tests.test_edit_translation.TestGetEditTranslationView`

To run the test app interactively, use `tox -e interactive`, visit `http://127.0.0.1:8020/admin/` and log in with `admin`/`changeme`.

## Support

For support, please use [GitHub Discussions](https://github.com/wagtail/wagtail-localize/discussions) or ask a question on the `#multi-language` channel on [Wagtail's Slack instance](https://wagtail.org/slack/).

## Thanks

Many thanks to all of our supporters, contributors, and early adopters who helped with the initial release. In particular, to The Mozilla Foundation and Torchbox who sponsored the majority of the initial development and Wagtail core's internationalisation support.

<!--content-end-->
