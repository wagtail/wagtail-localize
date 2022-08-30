
from django.test import TestCase, override_settings

from wagtail_localize.machine_translators.deepl import DeepLTranslator


class TestDeeplTranslator(TestCase):
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR["CLASS"]="wagtail_localize.machine_translators.deepl.DeepLTranslator")
    def setUp(self):
        pass
    
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR["OPTIONS"]["AUTH_KEY"]="asd-23-ssd-243-adsf-dummy-auth-key:fx")
    def test_free_api_endpoint(self):
        free_api_endpoint = DeepLTranslator({}).get_api_endpoint()
        self.assertEqual(free_api_endpoint, "https://api-free.deepl.com/v2/translate")
    
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR["OPTIONS"]["AUTH_KEY"]="asd-23-ssd-243-adsf-dummy-auth-key:bla")
    def test_paid_api_endpoint(self):
        paid_api_endpoint = DeepLTranslator({}).get_api_endpoint()
        self.assertEqual(paid_api_endpoint, "https://api.deepl.com/v2/translate")
