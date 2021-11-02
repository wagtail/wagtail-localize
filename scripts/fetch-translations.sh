#!/bin/env bash

# Delete old translation files (except "en" which is the source translation)
find ../wagtail-localize -iname *.po ! -iwholename */en/* -delete

# Fetch new translations from transifex
tx pull -a --minimum-perc=1

# Clean the PO files using msgattrib
# This removes the following:
#  - Blank, fuzzy and obsolete translations
#  - The line numbers above each translation
# These things are only needed by translators (which they won't be seen by) and make the translation updates difficult to check
find ../wagtail-localize -iname *.po ! -iwholename */en/* -exec msgattrib --translated --no-fuzzy --no-obsolete --no-location -o {} {} \;
