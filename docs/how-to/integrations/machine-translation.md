# Machine translation

Wagtail Localize supports using a machine translator for translating whole pages at a time with a single button click.

They are configured using the ``WAGTAILLOCALIZE_MACHINE_TRANSLATOR`` setting, which must be set to a ``dict`` like the following:

``` python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    'CLASS': 'path.to.translator.Class',
    'OPTIONS': {
        # ... options here
    }
}
```

This document describes how to configure various machine translators, as well as implement your own integration.

## DeepL

Website: [https://www.deepl.com/](https://www.deepl.com/)

Note that You will need a pro account to get an API key.

``` python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    'CLASS': 'wagtail_localize.machine_translators.deepl.DeepLTranslator',
    'OPTIONS': {
        'AUTH_KEY': '<Your DeepL key here>',
    }
}
```

## Dummy

The dummy translator exists primarily for testing Wagtail Localize and it only reverses the strings that are passed to
it. But you might want to use it to try out the UI without having to sign up to any external services:

``` python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    'CLASS': 'wagtail_localize.machine_translators.dummy.DummyTranslator',
}
```

## Custom integrations

```python
from .base import BaseMachineTranslator


class CustomTranslator(BaseMachineTranslator):
    # This name is displayed to end users in the form: "Translate with {display_name}"
    display_name = "Custom translator"

    def translate(self, source_locale, target_locale, strings):
        # Translate something
        # source_locale and target_locale are both Locale objects.
        # strings are a list of StringValue instances (see https://www.wagtail-localize.org/ref/strings/#wagtail_localize.strings.StringValue)

        # This function must return a dict with source StringValue's as the keys and translations as the values.

        # For example, to translate HTML strings with a ``translate_html`` function, use:
        return {
            string: StringValue.from_translated_html(
                translate_html(string.get_translatable_html())
            )
            for string in strings
        }

        # If the service does not support HTML, use plain text instead:
        return {
            string: StringValue.from_plaintext(
                translate_text(string.render_text())
            )
            for string in strings
        }

    def can_translate(self, source_locale, target_locale):
        # Return True if this translator can translate between the given languages.
        return source_locale.language_code != target_locale.language_code
```
