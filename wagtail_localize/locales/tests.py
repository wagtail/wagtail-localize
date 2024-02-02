from django.contrib.messages import get_messages
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext_lazy
from wagtail.models import Locale
from wagtail.test.utils import WagtailTestUtils
from wagtail.utils.version import get_main_version

from wagtail_localize.locales.components import LOCALE_COMPONENTS
from wagtail_localize.models import LocaleSynchronization


@override_settings(WAGTAIL_CONTENT_LANGUAGES=[("en", "English"), ("fr", "French")])
class BaseLocaleTestCase(TestCase, WagtailTestUtils):
    def setUp(self):
        # Set up the test environment
        self.login()
        self.english = Locale.objects.get()

    def execute_request(
        self, method, view_name, *args, params=None, post_data=None, **kwargs
    ):
        # Helper method to execute HTTP requests
        url = reverse(view_name, args=args)
        params = params or {}
        post_data = post_data or {}

        if method == "GET":
            return self.client.get(url, params, **kwargs)
        elif method == "POST":
            return self.client.post(url, post_data, **kwargs)

    def assert_successful_response(self, response):
        # Helper method to assert a successful response (status code 200)
        self.assertEqual(response.status_code, 200)

    def assert_context_variables(self, response, variable_name, variable_type):
        # Helper method to assert the presence and type of context variables
        self.assertIn(variable_name, response.context)
        self.assertIsInstance(response.context[variable_name], variable_type)

    def assert_redirect_to_index(self, response):
        # Helper method to assert redirection to the index page
        self.assertRedirects(response, reverse("wagtaillocales:index"))


class TestLocaleIndexView(BaseLocaleTestCase):
    def test_simple(self):
        # Test if the index view renders successfully
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        self.assertTemplateUsed(response, "wagtaillocales/index.html")

    def test_context_variables(self):
        # Test if the context variables are present and have the expected types
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        self.assert_context_variables(response, "locales", QuerySet)
        self.assert_context_variables(response, "wagtail_version", str)

    def test_queryset_filtering(self):
        # Test if the queryset is filtered as expected
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        self.assertTrue(
            all(
                locale in Locale.all_objects.all()
                for locale in response.context["locales"]
            )
        )

    def test_page_title(self):
        # Test if the page title is set correctly
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        expected_page_title = gettext_lazy("Locales")
        self.assertEqual(response.context["page_title"], expected_page_title)

    def test_wagtail_version(self):
        # Test if the Wagtail version is set correctly
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        expected_wagtail_version = get_main_version()
        self.assertEqual(response.context["wagtail_version"], expected_wagtail_version)

    def test_get_locale_usage(self):
        # Test the get_locale_usage function with different scenarios
        # For example, test with a locale that has no pages and others

        # Create a unique locale for testing
        locale = Locale.all_objects.create(language_code="fr")
        self.assertEqual(locale.language_code, "fr")

        # Execute the request and check if the locale is present in the context
        response = self.execute_request("GET", "wagtaillocales:index")
        self.assert_successful_response(response)
        self.assertIn(locale, response.context["locales"])


class TestLocaleCreateView(BaseLocaleTestCase):
    def post(self, post_data=None):
        # Helper method for making POST requests to create a locale
        return self.client.post(reverse("wagtaillocales:add"), post_data or {})

    def test_default_language(self):
        # Ensure the default language is set up correctly
        self.assertEqual(self.english.language_code, "en")
        self.assertEqual(self.english.get_display_name(), "English")

    def test_simple(self):
        # Test if the create view renders successfully with correct choices
        response = self.client.get(reverse("wagtaillocales:add"))
        self.assert_successful_response(response)
        self.assertTemplateUsed(response, "wagtaillocales/create.html")
        self.assertEqual(
            response.context["form"].fields["language_code"].choices, [("fr", "French")]
        )

    def test_create(self):
        # Test creating a new locale with synchronization
        post_data = {
            "language_code": "fr",
            "component-wagtail_localize_localesynchronization-enabled": "on",
            "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
        }

        response = self.post(post_data)

        # Should redirect back to index
        self.assert_redirect_to_index(response)
        self.assertRedirects(response, reverse("wagtaillocales:index"))

        # Check that the locale was created
        self.assertTrue(Locale.objects.filter(language_code="fr").exists())

        # Check the sync_from was set
        self.assertTrue(
            LocaleSynchronization.objects.filter(
                locale__language_code="fr", sync_from__language_code="en"
            ).exists()
        )

    def test_required_component_behavior(self):
        # Test behavior when a required component is not provided
        LOCALE_COMPONENTS[0]["required"] = True
        try:
            response = self.post({"language_code": "fr"})
        finally:
            LOCALE_COMPONENTS[0]["required"] = False

        self.assert_successful_response(response)
        self.assertIn("component_form", response.context)
        self.assertIn("sync_from", response.context["component_form"].errors)
        self.assertEqual(
            response.context["component_form"].errors["sync_from"],
            ["This field is required."],
        )

    def test_create_view_success_message(self):
        # Send a POST request to the create locale view
        response = self.post({"language_code": "fr"})

        # Check that the response status code is a redirect (302)
        self.assertEqual(response.status_code, 302)

        # Follow the redirect to the new page
        redirected_response = self.client.get(response.url, follow=True)

        # Now, check that the redirected response contains the expected success message
        self.assertContains(redirected_response, "Locale &#x27;French&#x27; created.")

    def test_duplicate_not_allowed(self):
        # Test creating a locale with a duplicate language code
        response = self.post(
            {
                "language_code": "en",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        form = response.context["form"]
        self.assertIn("language_code", form.errors)
        self.assertEqual(
            form.errors["language_code"],
            ["Select a valid choice. en is not one of the available choices."],
        )

    def test_language_code_must_be_in_settings(self):
        # Test creating a locale with an invalid language code
        response = self.post(
            {
                "language_code": "ja",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        form = response.context["form"]
        self.assertIn("language_code", form.errors)
        self.assertEqual(
            form.errors["language_code"],
            ["Select a valid choice. ja is not one of the available choices."],
        )

    def test_sync_from_required_when_enabled(self):
        # Test creating a locale with synchronization enabled and missing sync_from
        response = self.post(
            {
                "language_code": "fr",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": "",
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        component_form = response.context["component_form"]
        self.assertIn("sync_from", component_form.errors)
        self.assertEqual(
            component_form.errors["sync_from"], ["This field is required."]
        )

        # Check that the locale was not created
        self.assertFalse(Locale.objects.filter(language_code="fr").exists())

    def test_sync_from_not_required_when_disabled(self):
        # Test creating a locale with synchronization disabled
        response = self.post(
            {
                "language_code": "fr",
                "component-wagtail_localize_localesynchronization-enabled": "",
                "component-wagtail_localize_localesynchronization-sync_from": "",
            }
        )

        # Should redirect back to index
        self.assertRedirects(response, reverse("wagtaillocales:index"))

        # Check that the locale was created
        self.assertTrue(Locale.objects.filter(language_code="fr").exists())

        # Check the sync_from was not set
        self.assertFalse(LocaleSynchronization.objects.exists())

    def test_sync_from_required_when_component_required(self):
        # Test creating a locale with synchronization component required
        LOCALE_COMPONENTS[0]["required"] = True
        try:
            response = self.post(
                {
                    "language_code": "fr",
                    "component-wagtail_localize_localesynchronization-enabled": "",
                    "component-wagtail_localize_localesynchronization-sync_from": "",
                }
            )
        finally:
            LOCALE_COMPONENTS[0]["required"] = False

        # Should return the form with errors
        self.assert_successful_response(response)
        component_form = response.context["component_form"]
        self.assertIn("sync_from", component_form.errors)
        self.assertEqual(
            component_form.errors["sync_from"], ["This field is required."]
        )

        # Check that the locale was not created
        self.assertFalse(Locale.objects.filter(language_code="fr").exists())


class TestLocaleEditView(BaseLocaleTestCase):
    def post(self, post_data=None, locale=None):
        # Helper method for making POST requests to edit a locale
        post_data = post_data or {}
        locale = locale or self.english
        post_data.setdefault("language_code", locale.language_code)
        return self.client.post(
            reverse("wagtaillocales:edit", args=[locale.id]), post_data
        )

    def test_simple(self):
        # Test rendering the edit view with simple data
        response = self.client.get(
            reverse("wagtaillocales:edit", args=[self.english.id])
        )
        self.assert_successful_response(response)
        self.assertTemplateUsed(response, "wagtaillocales/edit.html")

        # Check choices in the form, including the current value
        self.assertEqual(
            response.context["form"].fields["language_code"].choices,
            [
                (
                    "en",
                    "English",
                ),  # Note: Current value is displayed even though it's in use
                ("fr", "French"),
            ],
        )

    def test_invalid_language(self):
        # Test editing with an invalid language code
        invalid = Locale.objects.create(language_code="foo")

        response = self.client.get(
            reverse("wagtaillocales:edit", kwargs={"pk": invalid.pk})
        )
        self.assert_successful_response(response)

        # Check choices in the form, showing a default if invalid
        self.assertEqual(
            response.context["form"].fields["language_code"].choices,
            [
                (
                    None,
                    "Select a new language",
                ),  # This is shown instead of the current value if invalid
                ("fr", "French"),
            ],
        )

    def test_edit(self):
        # Test editing a locale with synchronization
        response = self.post(
            {
                "language_code": "fr",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            }
        )

        # Should redirect back to index
        self.assert_redirect_to_index(response)
        self.assertRedirects(response, reverse("wagtaillocales:index"))

        # Check that the locale was edited
        self.english.refresh_from_db()
        self.assertEqual(self.english.language_code, "fr")

    def test_edit_view_success_message(self):
        # Test displaying a success message after editing a locale
        french_locale = Locale.objects.create(language_code="fr")

        response = self.client.post(
            reverse("wagtaillocales:edit", args=[french_locale.id]),
            {"language_code": "fr"},  # Change this to the actual language code
            follow=True,  # Follow redirects in the initial response
        )

        # Check that the response status code is 200 (OK)
        self.assert_successful_response(response)

        # Check that the redirected response contains the expected success message
        expected_success_message = "Locale &#x27;French&#x27; updated."  # Change this based on your expectations
        self.assertContains(response, expected_success_message)

    def test_edit_duplicate_not_allowed(self):
        # Test editing a locale with a duplicate language code
        french = Locale.objects.create(language_code="fr")

        response = self.post(
            {
                "language_code": "en",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            },
            locale=french,
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        form = response.context["form"]
        self.assertIn("language_code", form.errors)
        self.assertEqual(
            form.errors["language_code"],
            ["Select a valid choice. en is not one of the available choices."],
        )

    def test_edit_language_code_must_be_in_settings(self):
        # Test editing a locale with an invalid language code
        response = self.post(
            {
                "language_code": "ja",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        form = response.context["form"]
        self.assertIn("language_code", form.errors)
        self.assertEqual(
            form.errors["language_code"],
            ["Select a valid choice. ja is not one of the available choices."],
        )

    def test_sync_from_required_when_enabled(self):
        # Test editing a locale with synchronization enabled and missing sync_from
        response = self.post(
            {
                "language_code": "fr",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": "",
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        component_form = response.context["component_form"]
        self.assertIn("sync_from", component_form.errors)
        self.assertEqual(
            component_form.errors["sync_from"], ["This field is required."]
        )

    def test_sync_from_not_required_when_disabled(self):
        # Test editing a locale with synchronization disabled
        response = self.post(
            {
                "language_code": "fr",
                "component-wagtail_localize_localesynchronization-enabled": "",
                "component-wagtail_localize_localesynchronization-sync_from": "",
            }
        )

        # Should redirect back to index
        self.assert_redirect_to_index(response)

        # Check that the locale was edited
        self.english.refresh_from_db()
        self.assertEqual(self.english.language_code, "fr")

    def test_sync_from_required_when_component_required(self):
        # Test editing a locale with synchronization component required
        LOCALE_COMPONENTS[0]["required"] = True
        try:
            response = self.post(
                {
                    "language_code": "fr",
                    "component-wagtail_localize_localesynchronization-enabled": "",
                    "component-wagtail_localize_localesynchronization-sync_from": "",
                }
            )
        finally:
            LOCALE_COMPONENTS[0]["required"] = False

        # Should return the form with errors
        self.assert_successful_response(response)
        component_form = response.context["component_form"]
        self.assertIn("sync_from", component_form.errors)
        self.assertEqual(
            component_form.errors["sync_from"], ["This field is required."]
        )

    def test_sync_from_cannot_be_the_same_as_locale(self):
        # Test editing a locale with synchronization where sync_from is the same as the locale
        response = self.post(
            {
                "language_code": "en",
                "component-wagtail_localize_localesynchronization-enabled": "on",
                "component-wagtail_localize_localesynchronization-sync_from": self.english.id,
            }
        )

        # Should return the form with errors
        self.assert_successful_response(response)
        component_form = response.context["component_form"]
        self.assertIn("sync_from", component_form.errors)
        self.assertEqual(
            component_form.errors["sync_from"],
            ["This locale cannot be synced into itself."],
        )


class TestLocaleDeleteView(BaseLocaleTestCase):
    def follow_redirect(self, response):
        # Helper method to follow redirects in the response
        return self.client.get(response.url, follow=True)

    def post(self, post_data=None, locale=None):
        # Helper method for making POST requests to delete a locale
        locale = locale or self.english

        if post_data is not None:
            # Test case: both post_data and locale provided
            return self.client.post(
                reverse("wagtaillocales:delete", args=[locale.id]), post_data
            )
        else:
            # Test case: only locale provided
            return self.client.post(reverse("wagtaillocales:delete", args=[locale.id]))

    # Additional test cases for the post method
    def test_post_with_post_data(self):
        # Test making a POST request with both post_data and locale
        post_data = {"key": "value"}
        response = self.post(post_data=post_data, locale=self.english)
        # Add assertions based on the expected behavior
        self.assert_successful_response(response)

    def test_post_without_post_data(self):
        # Test making a POST request with only locale
        response = self.post(locale=self.english)
        # Add assertions based on the expected behavior
        self.assert_successful_response(response)

    def test_simple(self):
        # Test that the delete view renders the confirmation template
        response = self.execute_request("GET", "wagtaillocales:delete", self.english.id)
        self.assert_successful_response(response)
        self.assertTemplateUsed(response, "wagtailadmin/generic/confirm_delete.html")

    def test_delete_locale(self):
        # Test deleting a locale
        french = Locale.objects.create(language_code="fr")

        response = self.execute_request("POST", "wagtaillocales:delete", french.id)
        redirected_response = self.follow_redirect(response)

        # Check if the redirected response was successful (HTTP 302 - Found)
        self.assert_successful_response(redirected_response)

        # Check that the locale was deleted
        self.assertFalse(Locale.objects.filter(language_code="fr").exists())
        self.assertRedirects(response, reverse("wagtaillocales:index"))

    def test_cannot_delete_locales_with_pages(self):
        # Test attempting to delete a locale with associated pages
        response = self.execute_request(
            "POST", "wagtaillocales:delete", self.english.id
        )

        self.assert_successful_response(response)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].level_tag, "error")
        self.assertEqual(
            messages[0].message,
            "This locale cannot be deleted because there are pages and/or other objects using it.\n\n\n\n\n",
        )
        self.assertTrue(Locale.objects.filter(language_code="en").exists())

    def test_delete_locale_success_message(self):
        # Test success message after deleting a locale
        french = Locale.objects.create(language_code="fr")

        response = self.execute_request("POST", "wagtaillocales:delete", french.id)
        redirected_response = self.follow_redirect(response)

        # Check if the delete request was successful (HTTP 302 - Found)
        self.assert_successful_response(redirected_response)

        # Check that the redirected response contains the expected success message
        expected_message = "Locale &#x27;French&#x27; deleted."
        self.assertContains(redirected_response, expected_message)
