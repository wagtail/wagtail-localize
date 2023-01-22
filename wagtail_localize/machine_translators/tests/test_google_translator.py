from unittest import mock

from django.test import TestCase, override_settings

from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.machine_translators.google import GoogleCloudTranslator


SETTINGS_WITH_CREDENTIALS = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator",
    "OPTIONS": {
        # NB: These creds are completely fake/invalid. Don't bother trying them :)
        "CREDENTIALS": {
            "type": "service_account",
            "project_id": "wagtail-localize",
            "private_key_id": "fd019f02bdafaeae72101bdd1e79bce246af7893",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9x0BAQEFAAJRBKgwggSkAgEAAoIBAQCluNXi9W4tzqtP\no78Yj/84MN/lwuqFYs3DwBP5v8GdOamOyQ2t3D/NrDQhmd56jAQx6MpkFQyvr8dc\n7FH49/q/BQ892ZnHLQgsi33xg+12zLtObX3Ouxv1dO0pzcNfCf04xO+1CicrBV4Q\nla6HO03fr54VgDyORMCd8L7UKY92aoh41BBRlm2VXF+bS/oT5ZDw3QZc/n4xx0EG\nKv3xOGvp2G8DPMzIGO1BqqtWt7UT7YidLMB+PvbMhxggruW9TgVoh3bKpLzKALuj\nJx+dyulFbT2A4DHFKXH17BdtukZhHu8EmrsIwysFyfhosuuCPhQMm7iyRhFQW7Gg\nUi3O86dTAgMBAAECggEAFbTQv0e+hc+8umFBdVHFhvGqMKnpevuJussZs8kGPRAM\ntcNHAePLFw/8SFL4DI1kRX9IAhOdi5+bdOOPU4LbngYrZuQDyf5BxSeduRAjmKjT\npT6JuT6PNJyyOoBDR9Yh0Y9LRVcqJqONy3jfod/UCmsElHHeP+nhfTb8H2MTw6c7\nQDorF2i8OWPAxkrPLsojZ5jNX2GJLmgMjTLMNxZBye5kr/ubNw8sKT1mZ/2V0dZN\nI8XvBIY8Xvxbk0/0mdXVFoPWa8rrZaVkSb7GWpiBFr9E4kxIklSskPwf20ZvP3t8\nYvi4oGp/FqIPD7eCiWTvz8VuFZLjNa2hOa7al1OpgQKBgQDV06Oaq0K2+Zh1uNen\n4jLbvqtjRDPF6gkcEgcyoA0LjIdB6chR36DjWIOL2+kR61/MEx7lOAQwMIwDdhX5\nRj+4bA+8AhQq3cu3Gm5yZt++YCyFAjnwHXFcu09gRY9ucdo+bBDGJW/mDluVjmyL\n0EoasLtNPem/ipQEd/xBKGDm0wKBgQDGFuwMD3zCUjjLk8qcDs/oAUXAQEBZT1BJ\nNlGx4f2Z5N89Iw27Fod0oHNVIejM3tZUF22nWmEy0x9D8GEE08MbPJ//Rt6siNl0\n7i6/B1zCKN2zQJky9niwryVHKpmpAcBomzSb14kjGUBLMDA5P6SRbaAPf91Q3hD0\nlVMQFRrtgQKBgQCfk/kPXyzE/XVotfBMHKY0FRI3XRj+ZXEy/8lbYNMbgV8YM+8K\nG0kpIk/aOt6wPucZmFOAYdPOWwzDMIepp2G6svrzJuICM9Dq79DplBj7LS9MfKLc\nrjyCJlBQ2tj2ZgWofGHwXtQp7yEudkJP/bywOqEuPjyKdFOPGjSqNAZNfQKBgQCx\nQIOZyyX08AP4TlfnSu3JCZJzlErAX9NUn7F8fd8inQURPNOljGRK/OQW0o/w+plI\nh+pL7Pi6tOXuMiNuYVrdfWMh1zWbp50GH7deomTjLBQtuOkdDCU03JR72OfErleQ\ngwkRRk1lRcwdO5J7N7K3myO1mtHb8cm0QgYghvIggQKBgArV0YOtcJuMfl/Kx9oI\nuBjnu0HVGbS4T9TUJR1AKrmyZx7CTZQcW+CDQa4bV8NBCI4PPJwY1kHrYQdHyHK1\nv9c/0mRa/pimNmd2phQ7HzspYEX9ZK+/MMe0XMSC77Ur1vRS+9kt6upJ2g0k9+EX\nF6mJU6EuadZjUpFCaWvVK0rE\n-----END PRIVATE KEY-----\n",
            "client_email": "dummy@wagtail-localize.iam.gserviceaccount.com",
            "client_id": "110902095920514903541",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dummy%40wagtail-localize.iam.gserviceaccount.com",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }
    },
}

SETTINGS_WITH_CREDENTIALS_PATH = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator",
    "OPTIONS": {"CREDENTIALS_PATH": "/app/secrets/google-translate.json"},
}

SETTINGS_WITHOUT_CREDENTIALS = {
    "CLASS": "wagtail_localize.machine_translators.google.GoogleCloudTranslator"
}


class TestCloudTranslateTranslator(TestCase):
    @mock.patch(
        "wagtail_localize.machine_translators.google.translate.TranslationServiceClient.__init__",
        return_value=None,
    )
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=SETTINGS_WITHOUT_CREDENTIALS)
    def test_no_credentials_option_initialisation(self, translationsserviceclient_init):
        translator = get_machine_translator()
        self.assertIsInstance(translator, GoogleCloudTranslator)
        translator.client
        translationsserviceclient_init.assert_called_once_with()

    @mock.patch(
        "wagtail_localize.machine_translators.google.service_account.Credentials.from_service_account_info",
        return_value="MOCKED",
    )
    @mock.patch(
        "wagtail_localize.machine_translators.google.translate.TranslationServiceClient.__init__",
        return_value=None,
    )
    @override_settings(WAGTAILLOCALIZE_MACHINE_TRANSLATOR=SETTINGS_WITH_CREDENTIALS)
    def test_credentials_option_initialisation(
        self, translationsserviceclient_init, from_service_account_info
    ):
        translator = get_machine_translator()
        self.assertIsInstance(translator, GoogleCloudTranslator)
        translator.client
        from_service_account_info.assert_called_once_with(
            SETTINGS_WITH_CREDENTIALS["OPTIONS"]["CREDENTIALS"]
        )
        translationsserviceclient_init.assert_called_once_with(credentials="MOCKED")

    @mock.patch(
        "wagtail_localize.machine_translators.google.service_account.Credentials.from_service_account_file",
        return_value="MOCKED",
    )
    @mock.patch(
        "wagtail_localize.machine_translators.google.translate.TranslationServiceClient.__init__",
        return_value=None,
    )
    @override_settings(
        WAGTAILLOCALIZE_MACHINE_TRANSLATOR=SETTINGS_WITH_CREDENTIALS_PATH
    )
    def test_credentials_path_option_initialisation(
        self, translationsserviceclient_init, from_service_account_file
    ):
        translator = get_machine_translator()
        self.assertIsInstance(translator, GoogleCloudTranslator)
        translator.client
        from_service_account_file.assert_called_once_with(
            SETTINGS_WITH_CREDENTIALS_PATH["OPTIONS"]["CREDENTIALS_PATH"]
        )
        translationsserviceclient_init.assert_called_once_with(credentials="MOCKED")
