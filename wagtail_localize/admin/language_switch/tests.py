import json

from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.models import Language, Region, Locale
from wagtail_localize.test.models import TestPage


class TestTranslationsListView(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()

        french_language = Language.objects.create(code="fr")
        french_locale = Locale.objects.get(
            language=french_language, region=Region.objects.default()
        )

        self.root_page = Page.objects.get(depth=1)

        self.test_page = self.root_page.add_child(instance=TestPage(title="Test page"))
        self.test_page_french = self.test_page.copy_for_translation(french_locale)

    def test(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_language_switch:translations_list",
                args=[self.test_page.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertHTMLEqual(
            data["html"],
            """
            <header class="  " role="banner">
                <div class="row nice-padding">
                    <div class="left">
                        <div class="col header-title">
                            <h1 class="icon icon-">Translations <span>Test page</span></h1>
                        </div>
                    </div>
                    <div class="right"></div>
                </div>
            </header>
            <div class="nice-padding">
                <table class="listing">
                    <thead>
                        <tr class="table-headers">
                            <th>Language</th>
                            <th>Page</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>English</td>
                            <td class="title">Test page</td>
                            <td class="listing__item--active"><b>Current page</b></td>
                        </tr>
                        <tr>
                            <td>French</td>
                            <td class="title">Test page</td>
                            <td class="listing__item--active">
                                <ul class="actions">
                                    <li>
                                        <a href="{edit_french_url}" class="button button-small button-secondary">Edit</a>
                                    </li>
                                    <li>
                                        <a href="{view_french_url}" class="button button-small button-secondary" target="_blank" rel="noopener noreferrer">View draft</a>
                                    </li>
                                </ul>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        """.format(
                edit_french_url=reverse(
                    "wagtailadmin_pages:edit", args=[self.test_page_french.id]
                ),
                view_french_url=reverse(
                    "wagtailadmin_pages:view_draft", args=[self.test_page_french.id]
                ),
            ),
        )

    def test_for_non_translatable_page(self):
        response = self.client.get(
            reverse(
                "wagtail_localize_language_switch:translations_list",
                args=[self.root_page.id],
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
