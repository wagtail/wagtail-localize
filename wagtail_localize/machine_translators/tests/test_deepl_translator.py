from django.test import TestCase, override_settings

from wagtail_localize.machine_translators.deepl import DeepLTranslator


DEEPL_SETTINGS_FREE_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.dummy.DummyTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:fx"},
}

DEEPL_SETTINGS_PAID_ENDPOINT = {
    "CLASS": "wagtail_localize.machine_translators.dummy.DummyTranslator",
    "OPTIONS": {"AUTH_KEY": "asd-23-ssd-243-adsf-dummy-auth-key:bla"},
}


class TestDeeplTranslator(TestCase):
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_FREE_ENDPOINT)
    def test_free_api_endpoint(self):
        free_api_endpoint = DeepLTranslator({}).get_api_endpoint()
        self.assertEqual(free_api_endpoint, "https://api-free.deepl.com/v2/translate")

    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=DEEPL_SETTINGS_PAID_ENDPOINT)
    def test_paid_api_endpoint(self):
        paid_api_endpoint = DeepLTranslator({}).get_api_endpoint()
        self.assertEqual(paid_api_endpoint, "https://api.deepl.com/v2/translate")
