from urllib.parse import urlencode

from django.contrib.admin.utils import quote
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from django.urls import reverse
from wagtail.core.models import Locale, Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.modeladmin import ModelAdmin, TranslatableModelAdmin, helpers
from wagtail_localize.modeladmin.views import (
    TranslatableIndexView,
    TranslatableInspectView,
)
from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.test.models import NonTranslatableModel, TestModel, TestPage
from wagtail_localize.test.wagtail_hooks import TestModelAdmin, TestPageAdmin


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
            '<a href="/admin/wagtail_localize_test/testmodel/edit/{}/"'.format(
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
            )
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
            )
        )


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

    def test_helper_getters(self):
        # Test model admin helpers
        self.assertEqual(
            self.model_admin.get_permission_helper_class(),
            helpers.TranslatablePermissionHelper,
        )
        self.assertEqual(
            self.model_admin.get_url_helper_class(),
            helpers.TranslatableAdminURLHelper,
        )
        self.assertEqual(
            self.model_admin.get_button_helper_class(),
            helpers.TranslatableButtonHelper,
        )
        # Test overriden model admin helpers
        self.model_admin.permission_helper_class = helpers.PermissionHelper
        self.model_admin.url_helper_class = helpers.AdminURLHelper
        self.model_admin.button_helper_class = helpers.ButtonHelper
        self.assertEqual(
            self.model_admin.get_permission_helper_class(),
            helpers.PermissionHelper,
        )
        self.assertEqual(
            self.model_admin.get_url_helper_class(),
            helpers.AdminURLHelper,
        )
        self.assertEqual(
            self.model_admin.get_button_helper_class(),
            helpers.ButtonHelper,
        )
        # Test page admin helpers
        self.assertEqual(
            self.page_admin.get_permission_helper_class(),
            helpers.TranslatablePagePermissionHelper,
        )
        self.assertEqual(
            self.page_admin.get_url_helper_class(),
            helpers.TranslatablePageAdminURLHelper,
        )
        self.assertEqual(
            self.page_admin.get_button_helper_class(),
            helpers.TranslatablePageButtonHelper,
        )

    def test_get_templates(self):
        def result(action):
            return [
                "modeladmin/wagtail_localize_test/testmodel/translatable_%s.html" % action,
                "modeladmin/wagtail_localize_test/translatable_%s.html" % action,
                "modeladmin/translatable_%s.html" % action,
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
        self.modeladmin_page_source, created = TranslationSource.get_or_create_from_instance(
            self.en_modeladmin_page
        )
        self.modeladmin_page_translation = Translation.objects.create(
            source=self.modeladmin_page_source, target_locale=self.fr_locale
        )
        self.modeladmin_page_translation.save_target(publish=True)

    def test_permission_helper(self):
        helper = self.page_admin.get_permission_helper_class()(TestPage)
        pages = helper.get_valid_parent_pages(self.user)
        self.assertEqual(len(pages), 3)
        helper.locale = self.en_locale
        pages = helper.get_valid_parent_pages(self.user)
        self.assertEqual(len(pages), 2)

    def test_url_helper(self):
        helper = self.model_admin.get_url_helper_class()(TestModel)
        self.assertNotIn("?locale=en", helper.get_action_url("create"))
        helper.locale = self.en_locale
        self.assertIn("?locale=en", helper.get_action_url("create"))
        self.assertIn("?locale=en", helper.get_action_url("index"))
        self.assertNotIn(
            "?locale=en",
            helper.get_action_url("edit", instance_pk=self.en_modeladmin.pk),
        )

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
                    "wagtail_localize:submit_modeladmin_translation",
                    args=[
                        self.en_modeladmin._meta.app_label,
                        self.en_modeladmin._meta.model_name,
                        quote(self.en_modeladmin.pk),
                    ],
                ),
                "label": "Translate",
                "classname": "button-class",
                "title": "Translate",
            }
        )
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize:update_translations",
                    args=[self.modeladmin_source.pk],
                ) + "?" + urlencode({"next": "/next/url/"}),
                "label": "Sync translated test models",
                "classname": "button-class",
                "title": "Sync translated test models",
            }
        )

        with self.assertRaises(StopIteration):
            next(btns)

    def test_get_translation_buttons_for_page(self):
        btns = helpers.get_translation_buttons(self.en_modeladmin_page, self.user)
        self.assertEqual(
            next(btns),
            {
                "url": reverse(
                    "wagtail_localize:submit_modeladmin_translation",
                    args=[
                        self.en_modeladmin_page._meta.app_label,
                        self.en_modeladmin_page._meta.model_name,
                        quote(self.en_modeladmin_page.pk),
                    ],
                ),
                "label": "Translate",
                "classname": "",
                "title": "Translate",
            }
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
            }
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
            }
        )

        with self.assertRaises(StopIteration):
            next(btns)

    def test_get_translation_buttons_no_user_perms(self):
        strip_user_perms()

        self.user.refresh_from_db()
        btns = helpers.get_translation_buttons(self.en_modeladmin, self.user)

        with self.assertRaises(StopIteration):
            next(btns)
