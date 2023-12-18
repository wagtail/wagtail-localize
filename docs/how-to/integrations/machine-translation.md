# Machine translation

Wagtail Localize supports using a machine translator for translating whole pages at a time with a single button click.

They are configured using the `WAGTAILLOCALIZE_MACHINE_TRANSLATOR` setting, which must be set to a `dict` like the following:

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "path.to.translator.Class",
    "OPTIONS": {
        # ... options here
    },
}
```

This document describes how to configure various machine translators, as well as implement your own integration.

## Google Cloud Translation

Website: [https://cloud.google.com/translate](https://cloud.google.com/translate)

### 1. Install additional dependencies

Google Cloud Translate requires some optional dependencies. Install wagtail-localize with the google plugin:

```
pip install wagtail-localize[google]
```

### 2. Configure a service account

For you site to use the API, it will need to authenticate with Google Cloud in some way. Documentation for this can be found at [https://googleapis.dev/python/google-api-core/latest/auth.html](https://googleapis.dev/python/google-api-core/latest/auth.html).

The most common approach is to create a [Service account](https://cloud.google.com/iam/docs/creating-managing-service-accounts) for the relevant Project with the **Cloud Translation API User** role (to allow API requests to be made).

Once configured, you should be able to generate and download a [service account key file](https://cloud.google.com/iam/docs/creating-managing-service-account-keys) to use in the next step.

### 3. Configure wagtail-localize:

#### Using the `CREDENTIALS_PATH` option

When it is possible to make key files available securely in each environment, this is the recommended option, as it makes configuration a little more obvious when looking at your settings file.

This option value should be specified in your Django settings, like so:

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator",
    "OPTIONS": {
        "CREDENTIALS_PATH": "/path/to/keyfile.json",
        "PROJECT_ID": "<Your project ID here>",
    },
}
```

#### Using the `CREDENTIALS` option

If making key files available securely in each environment is not viable, you can use this option to make the same information available as a Python `dict`.

Adding something like the following to your Django settings would allow you to use different key values for each environment, which you may find useful:

```
import os

WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator",
    "OPTIONS": {
        "CREDENTIALS": {
            "type": "service_account",
            # These values are required, and will usually be unique
            # for each environment
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT_ID"),
            "private_key_id": os.environ.get("GOOGLE_CLOUD_PRIVATE_KEY_ID"),
            # NOTE: Should be provided as a multi-line string
            "private_key": os.environ.get("GOOGLE_CLOUD_PRIVATE_KEY"),
            "client_email": os.environ.get("GOOGLE_CLOUD_CLIENT_EMAIL"),
            "client_id": os.environ.get("GOOGLE_CLOUD_CLIENT_ID"),
            "client_x509_cert_url": os.environ.get("GOOGLE_CLOUD_CLIENT_CERT_URL"),
            # These values usually remain the same, but you should check
            # your key file(s) and override where necessary
            "auth_uri": os.environ.get(
                "GOOGLE_CLOUD_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
            ),
            "token_uri": os.environ.get(
                "GOOGLE_CLOUD_TOKEN_URI" "https://oauth2.googleapis.com/token"
            ),
            "auth_provider_x509_cert_url": os.environ.get(
                "GOOGLE_CLOUD_AUTH_PROVIDER_CERT_URL",
                "https://www.googleapis.com/oauth2/v1/certs",
            ),
        },
        "PROJECT_ID": "<Your project ID here>",
    },
}
```

#### Seting the `GOOGLE_APPLICATION_CREDENTIALS` env var

An alternative to the `CREDENTIALS_PATH` option is to set an env var value pointing to the correct key path.

```bash
GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
```

With this approach, the Python client will look for this value automatically when making translation requests, and all you should need to add to your Django settings is:

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator",
    "OPTIONS": {
        "PROJECT_ID": "<Your project ID here>",
    },
}
```

## DeepL

Website: [https://www.deepl.com/](https://www.deepl.com/)

Note that You will need a pro account to get an API key.

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.deepl.DeepLTranslator",
    "OPTIONS": {
        "AUTH_KEY": "<Your DeepL key here>",
    },
}
```

## LibreTranslate

Website: [https://libretranslate.com/](https://libretranslate.com/)

!!! note

    You will need a subscription to get an API key. Alternatively, you can host your own instance. See more details at [https://github.com/LibreTranslate/LibreTranslate](https://github.com/LibreTranslate/LibreTranslate).

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.libretranslate.LibreTranslator",
    "OPTIONS": {
        "LIBRETRANSLATE_URL": "https://libretranslate.org",  # or your self-hosted instance URL
        "API_KEY": "<Your LibreTranslate api key here>",  # Optional on self-hosted instance by providing a random string
    },
}
```

## Dummy

The dummy translator exists primarily for testing Wagtail Localize and it only reverses the strings that are passed to
it. But you might want to use it to try out the UI without having to sign up to any external services:

```python
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_localize.machine_translators.dummy.DummyTranslator",
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
            string: StringValue.from_plaintext(translate_text(string.render_text()))
            for string in strings
        }

    def can_translate(self, source_locale, target_locale):
        # Return True if this translator can translate between the given languages.
        return source_locale.language_code != target_locale.language_code
```
