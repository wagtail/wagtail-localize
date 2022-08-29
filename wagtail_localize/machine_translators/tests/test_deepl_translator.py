
from django.test import TestCase

from wagtail_localize.machine_translators.deepl import auth_key_is_free_account


class TestDeeplTranslator(TestCase):
    def setUp(self):
        self.free_auth_key = "asd-23-ssd-243-adsf-dummy-auth-key:fx"
        self.paid_auth_key = "asd-23-ssd-243-adsf-dummy-auth-key:bla"
    
    def test_api_free(self):
        self.assertEqual(auth_key_is_free_account(self.free_auth_key), True)
    
    def test_api_paid(self):
        self.assertEqual(auth_key_is_free_account(self.paid_auth_key), False)
