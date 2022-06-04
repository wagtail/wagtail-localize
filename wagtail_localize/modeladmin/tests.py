from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from wagtail.core.models import Locale, Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.modeladmin import helpers
from wagtail_localize.modeladmin.options import ModelAdmin, TranslatableModelAdmin
from wagtail_localize.modeladmin.views import (
    TranslatableIndexView,
    TranslatableInspectView,
)
from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.test.models import NonTranslatableModel, TestModel, TestPage
from wagtail_localize.test.wagtail_hooks import TestModelAdmin, TestPageAdmin
from wagtail_localize.tests.utils import assert_permission_denied


def strip_user_perms():
    """
    Removes user permissions so they can still access admin and edit pages but can't submit anything for translation.
    """
    editors_group = Group.objects.get(name="Editors")
    editors_group.permissions.filter(codename="submit_translation").delete()

    for permission in Permission.objects.filter(
        content_type=ContentType.objects.get_for_model(TestModel)
    ):
        editors_group.permissions.add(permission)

    user = get_user_model().objects.get()
    user.is_superuser = False
    user.groups.add(editors_group)
    user.save()


class TestModelAdminViews(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_modeladmin = TestModel.objects.create(title="Test modeladmin")
        self.modeladmin_source, created = TranslationSource.get_or_create_from_instance(
            self.en_modeladmin
        )
        self.modeladmin_translation = Translation.objects.create(
            source=self.modeladmin_source, target_locale=self.fr_locale
        )
        self.modeladmin_translation.save_target(publish=True)
        self.fr_modeladmin = self.en_modeladmin.get_translation(self.fr_locale)

    def test(self):
        with self.assertRaises(ImproperlyConfigured):
            TranslatableIndexView(
                model_admin=type(
                    "NonTranslatableModelAdmin",
                    (ModelAdmin,),
                    {"model": NonTranslatableModel},
                )()
            )

    def test_index_view(self):
        response = self.client.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )
        self.assertContains(response, "Translate")

    def test_create_view(self):
        create_url = reverse("wagtail_localize_test_testmodel_modeladmin_create")
        response = self.client.get(create_url)

        # Check for correct Form Action
        self.assertContains(
            response,
            '<form action="/admin/wagtail_localize_test/testmodel/create/?locale=en"',
        )

        # Check, if other Language is available in Dropdown
        self.assertContains(
            response,
            '<a href="/admin/wagtail_localize_test/testmodel/create/?locale=de"',
        )

        # Create a new DE object if and check for locale
        response = self.client.post(create_url + "?locale=de", {"title": "New model"})
        self.assertRedirects(
            response,
            reverse("wagtail_localize_test_testmodel_modeladmin_index") + "?locale=de",
        )
        obj = TestModel.objects.last()
        self.assertEqual(obj.title, "New model")
        self.assertEqual(obj.locale, self.de_locale)

    def test_edit_view(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.en_modeladmin.pk],
            )
        )
        self.assertContains(
            response,
            '<a href="/admin/wagtail_localize_test/testmodel/edit/{}/?locale=fr"'.format(
                self.fr_modeladmin.pk
            ),
        )

        # Check restart translation button is displayed
        self.modeladmin_translation.enabled = False
        self.modeladmin_translation.save()
        response = self.client.get(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.fr_modeladmin.pk],
            )
        )
        self.assertContains(response, "Start Synced translation")

        # Check restart translation triggers correctly
        response = self.client.post(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.fr_modeladmin.pk],
            ),
            {"localize-restart-translation": True},
        )
        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.fr_modeladmin.pk],
            ),
        )
        self.modeladmin_translation.refresh_from_db()
        self.assertTrue(self.modeladmin_translation.enabled)

        # Check existant FR translation renders the "edit_translation" view
        response = self.client.get(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.fr_modeladmin.pk],
            )
        )
        self.assertContains(
            response,
            "Translation of TestModel object ({}) into French".format(
                self.en_modeladmin.pk
            ),
        )

    def test_inspect_view(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_inspect",
                args=[self.en_modeladmin.pk],
            )
        )
        self.assertContains(
            response,
            '<a href="/admin/wagtail_localize_test/testmodel/inspect/{}/?locale=fr"'.format(
                self.fr_modeladmin.pk
            ),
        )
        self.assertContains(response, "Translate")
        self.assertContains(response, "Sync translated test models")

        # Create DE translation and check "Translate" button not showing
        Translation.objects.create(
            source=self.modeladmin_source, target_locale=self.de_locale
        ).save_target(publish=True)

        response = self.client.get(
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_inspect",
                args=[self.fr_modeladmin.pk],
            )
        )
        self.assertNotContains(response, "Translate")
        self.assertNotContains(response, "Sync translated test models")


class TestModelAdminAdmin(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()
        self.model_admin = TestModelAdmin()
        self.page_admin = TestPageAdmin()

    def test(self):
        with self.assertRaises(ImproperlyConfigured):
            type(
                "NonTranslatableModelAdmin",
                (TranslatableModelAdmin,),
                {"model": NonTranslatableModel},
            )()

    def test_button_helper_getter(self):
        self.assertEqual(
            self.model_admin.get_button_helper_class(),
            helpers.TranslatableButtonHelper,
        )
        self.model_admin.button_helper_class = helpers.ButtonHelper
        self.assertEqual(
            self.model_admin.get_button_helper_class(),
            helpers.ButtonHelper,
        )
        self.assertEqual(
            self.page_admin.get_button_helper_class(),
            helpers.TranslatablePageButtonHelper,
        )

    def test_get_templates(self):
        def result(action):
            return [
                "wagtail_localize/modeladmin/wagtail_localize_test/testmodel/translatable_%s.html"
                % action,
                "wagtail_localize/modeladmin/wagtail_localize_test/translatable_%s.html"
                % action,
                "wagtail_localize/modeladmin/translatable_%s.html" % action,
            ]

        self.assertEqual(self.model_admin.get_templates("index"), result("index"))
        self.assertEqual(self.model_admin.get_templates("create"), result("create"))
        self.assertEqual(self.model_admin.get_templates("edit"), result("edit"))
        self.assertEqual(self.model_admin.get_templates("inspect"), result("inspect"))
        self.assertEqual(self.model_admin.get_templates("delete"), result("delete"))
        self.assertEqual(
            self.model_admin.get_templates("choose_parent"), result("choose_parent")
        )


class TestModelAdminHelpers(TestCase, WagtailTestUtils):
    def setUp(self):
        self.user = self.login()
        self.factory = RequestFactory()

        self.model_admin = TestModelAdmin()
        self.page_admin = TestPageAdmin()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_modeladmin = TestModel.objects.create(title="Test modeladmin")
        self.modeladmin_source, created = TranslationSource.get_or_create_from_instance(
            self.en_modeladmin
        )
        self.modeladmin_translation = Translation.objects.create(
            source=self.modeladmin_source, target_locale=self.fr_locale
        )
        self.modeladmin_translation.save_target(publish=True)
        self.fr_modeladmin = self.en_modeladmin.get_translation(self.fr_locale)

        root_page = Page.objects.get(id=1)
        root_page.get_children().delete()
        root_page.refresh_from_db()

        self.en_modeladmin_page = root_page.add_child(instance=TestPage(title="Test"))
        (
            self.modeladmin_page_source,
            created,
        ) = TranslationSource.get_or_create_from_instance(self.en_modeladmin_page)
        self.modeladmin_page_translation = Translation.objects.create(
            source=self.modeladmin_page_source, target_locale=self.fr_locale
        )
        self.modeladmin_page_translation.save_target(publish=True)

    def test_button_helper(self):
        request = self.factory.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )
        request.user = self.user

        view = TranslatableIndexView(self.model_admin)
        helper = self.model_admin.get_button_helper_class()(view, request)
        buttons = helper.get_buttons_for_obj(self.en_modeladmin)
        self.assertEqual(
            buttons[-1]["classname"],
            "button button-secondary button-small",
        )

        # Check inspect view sets different button classes
        view = TranslatableInspectView(self.model_admin, str(self.en_modeladmin.pk))
        helper = self.model_admin.get_button_helper_class()(view, request)
        buttons = helper.get_buttons_for_obj(self.en_modeladmin)
        self.assertEqual(buttons[-1]["classname"], "button button-secondary")

    def test_get_translation_buttons(self):
        btns = helpers.get_translation_buttons(
            self.en_modeladmin, self.user, "/next/url/", "button-class"
        )
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize_modeladmin:submit_translation",
                    args=[
                        self.en_modeladmin._meta.app_label,
                        self.en_modeladmin._meta.model_name,
                        quote(self.en_modeladmin.pk),
                    ],
                ),
                "label": "Translate",
                "classname": "button-class",
                "title": "Translate",
            },
        )
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize:update_translations",
                    args=[self.modeladmin_source.pk],
                )
                + "?"
                + urlencode({"next": "/next/url/"}),
                "label": "Sync translated test models",
                "classname": "button-class",
                "title": "Sync translated test models",
            },
        )

        with self.assertRaises(StopIteration):
            next(btns)

    def test_get_translation_buttons_for_page(self):
        btns = helpers.get_translation_buttons(self.en_modeladmin_page, self.user)
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize_modeladmin:submit_translation",
                    args=[
                        self.en_modeladmin_page._meta.app_label,
                        self.en_modeladmin_page._meta.model_name,
                        quote(self.en_modeladmin_page.pk),
                    ],
                ),
                "label": "Translate",
                "classname": "",
                "title": "Translate",
            },
        )
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize:update_translations",
                    args=[self.modeladmin_page_source.pk],
                ),
                "label": "Sync translated test pages",
                "classname": "",
                "title": "Sync translated test pages",
            },
        )

        with self.assertRaises(StopIteration):
            next(btns)

    def test_get_translation_buttons_no_locale_to_translate_to(self):
        Translation.objects.create(
            source=self.modeladmin_source, target_locale=self.de_locale
        ).save_target(publish=True)

        btns = helpers.get_translation_buttons(self.en_modeladmin, self.user)
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize:update_translations",
                    args=[self.modeladmin_source.pk],
                ),
                "label": "Sync translated test models",
                "classname": "",
                "title": "Sync translated test models",
            },
        )

        with self.assertRaises(StopIteration):
            next(btns)

    def test_get_translation_buttons_no_user_perms(self):
        strip_user_perms()

        self.user.refresh_from_db()
        btns = helpers.get_translation_buttons(self.en_modeladmin, self.user)

        with self.assertRaises(StopIteration):
            next(btns)


@override_settings(
    LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
)
class TestTranslateModelAdminListingButton(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_modeladmin = TestModel.objects.create(
            title="Test modeladmin", test_textfield="Test modeladmin"
        )
        self.fr_modeladmin = self.en_modeladmin.copy_for_translation(self.fr_locale)
        self.fr_modeladmin.save()

        self.not_translatable_modeladmin = NonTranslatableModel.objects.create()

    def test(self):
        response = self.client.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )
        self.assertContains(
            response,
            (
                f'href="/admin/localize/modeladmin/submit/wagtail_localize_test/testmodel/{self.en_modeladmin.id}/" '
                f'class="button button-secondary button-small" title="Translate">Translate</a>'
            ),
        )

    def test_hides_if_modeladmin_already_translated(self):
        de_modeladmin = self.en_modeladmin.copy_for_translation(self.de_locale)
        de_modeladmin.save()

        response = self.client.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_modeladmin_isnt_translatable(self):
        de_modeladmin = self.en_modeladmin.copy_for_translation(self.de_locale)
        de_modeladmin.save()

        response = self.client.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )

        self.assertNotContains(response, "Translate")

    def test_hides_if_user_doesnt_have_permission(self):
        strip_user_perms()

        response = self.client.get(
            reverse("wagtail_localize_test_testmodel_modeladmin_index")
        )

        self.assertNotContains(response, "Translate")


@override_settings(
    LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
)
class TestSubmitModelAdminTranslation(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        self.en_modeladmin = TestModel.objects.create(
            title="Test modeladmin", test_textfield="Test modeladmin"
        )

        self.not_translatable_modeladmin = NonTranslatableModel.objects.create()

    def test_get_submit_modeladmin_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset),
            [self.de_locale, self.fr_locale],
        )

        # More than one locale so show "Select all"
        self.assertFalse(response.context["form"]["select_all"].field.widget.is_hidden)

        # ModelAdmin can't have children so hide include_subtree
        self.assertTrue(
            response.context["form"]["include_subtree"].field.widget.is_hidden
        )

    def test_get_submit_modeladmin_translation_when_not_modeladmin(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtailcore", "page", 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_modeladmin_translation_when_invalid_model(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtailcore", "foo", 1],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_modeladmin_translation_when_not_translatable(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=[
                    "wagtail_localize_test",
                    "nontranslatablemodel",
                    self.not_translatable_modeladmin.id,
                ],
            ),
            # Need to follow as Django will initiall redirect to /en/admin/
            follow=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_get_submit_modeladmin_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            )
        )

        assert_permission_denied(self, response)

    def test_get_submit_modeladmin_translation_when_already_translated(self):
        # Locales that have been translated into shouldn't be included
        translation = self.en_modeladmin.copy_for_translation(self.de_locale)
        translation.save()

        response = self.client.get(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertListEqual(
            list(response.context["form"]["locales"].field.queryset), [self.fr_locale]
        )

        # Since there is only one locale, the "Select All" checkbox should be hidden
        self.assertTrue(response.context["form"]["select_all"].field.widget.is_hidden)

    def test_post_submit_modeladmin_translation(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        translation = Translation.objects.get()
        self.assertEqual(translation.source.locale, self.en_locale)
        self.assertEqual(translation.target_locale, self.fr_locale)
        self.assertTrue(translation.created_at)

        # The translated modeladmin should've been created
        translated_modeladmin = self.en_modeladmin.get_translation(self.fr_locale)
        self.assertEqual(translated_modeladmin.test_textfield, "Test modeladmin")

        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[translated_modeladmin.id],
            ),
        )

    def test_post_submit_modeladmin_translation_into_multiple_locales(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            ),
            {"locales": [self.fr_locale.id, self.de_locale.id]},
        )

        self.assertRedirects(
            response,
            reverse(
                "wagtail_localize_test_testmodel_modeladmin_edit",
                args=[self.en_modeladmin.id],
            ),
        )

        # Check French translation
        fr_translation = Translation.objects.get(target_locale=self.fr_locale)
        self.assertEqual(fr_translation.source.locale, self.en_locale)
        self.assertTrue(fr_translation.created_at)

        # Check German translation
        de_translation = Translation.objects.get(target_locale=self.de_locale)
        self.assertEqual(de_translation.source.locale, self.en_locale)
        self.assertTrue(de_translation.created_at)

    def test_post_submit_modeladmin_translation_with_missing_locale(self):
        response = self.client.post(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            ),
            {"locales": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Translation.objects.exists())
        self.assertFormError(response, "form", "locales", ["This field is required."])

    def test_post_submit_modeladmin_translation_without_permissions(self):
        strip_user_perms()

        response = self.client.post(
            reverse(
                "wagtail_localize_modeladmin:submit_translation",
                args=["wagtail_localize_test", "testmodel", self.en_modeladmin.id],
            ),
            {"locales": [self.fr_locale.id]},
        )

        assert_permission_denied(self, response)


@override_settings(
    LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
    WAGTAIL_CONTENT_LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ],
)
class TestUpdateModelAdminTranslations(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        self.en_locale = Locale.objects.get()
        self.fr_locale = Locale.objects.create(language_code="fr")
        self.de_locale = Locale.objects.create(language_code="de")

        # Create modeladmin object and FR translation
        self.en_modeladmin = TestModel.objects.create(
            title="Test modeladmin", test_textfield="Test modeladmin"
        )
        self.modeladmin_source, created = TranslationSource.get_or_create_from_instance(
            self.en_modeladmin
        )
        self.modeladmin_translation = Translation.objects.create(
            source=self.modeladmin_source, target_locale=self.fr_locale
        )
        self.modeladmin_translation.save_target(publish=True)
        self.fr_modeladmin = self.en_modeladmin.get_translation(self.fr_locale)

    def test_get_update_modeladmin_translation(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.modeladmin_source.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["translations"],
            [
                {
                    "title": str(self.fr_modeladmin),
                    "locale": self.fr_locale,
                    "edit_url": reverse(
                        "wagtail_localize_test_testmodel_modeladmin_edit",
                        args=[self.fr_modeladmin.id],
                    ),
                }
            ],
        )

    def test_post_update_modeladmin_translation(self):
        self.en_modeladmin.test_textfield = "Edited modeladmin"
        self.en_modeladmin.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.modeladmin_source.id],
            )
        )

        self.assertRedirects(
            response,
            reverse("wagtail_localize_test_testmodel_modeladmin_index"),
        )

        # The FR version shouldn't be updated yet
        self.fr_modeladmin.refresh_from_db()
        self.assertEqual(self.fr_modeladmin.test_textfield, "Test modeladmin")

    def test_post_update_modeladmin_translation_with_publish_translations(self):
        self.en_modeladmin.test_textfield = "Edited modeladmin"
        self.en_modeladmin.save()

        response = self.client.post(
            reverse(
                "wagtail_localize:update_translations",
                args=[self.modeladmin_source.id],
            ),
            {"publish_translations": "on"},
        )

        self.assertRedirects(
            response,
            reverse("wagtail_localize_test_testmodel_modeladmin_index"),
        )

        # The FR version should be updated
        self.fr_modeladmin.refresh_from_db()
        self.assertEqual(self.fr_modeladmin.test_textfield, "Edited modeladmin")
