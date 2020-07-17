import json

from django.test import TestCase
from django.urls import reverse
from wagtail.core.models import Page, Locale
from wagtail.tests.utils import WagtailTestUtils

from wagtail_localize.test.models import TestPage

from wagtail import VERSION as WAGTAIL_VERSION


class TestTranslationsListView(TestCase, WagtailTestUtils):
    maxDiff = None

    def setUp(self):
        self.login()

        french_locale = Locale.objects.create(language_code="fr")

        self.root_page = Page.objects.get(depth=1)

        self.test_page = self.root_page.add_child(instance=TestPage(title="Test page"))
        self.test_page_french = self.test_page.copy_for_translation(french_locale)

    def test(self):
        response = self.client.get(
            reverse(
                "wagtail_localize:translations_list_modal",
                args=[self.test_page.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertHTMLEqual(
            data["html"],
            """
            <header class="  " """ + ('role="banner"' if WAGTAIL_VERSION < (2, 9) else "") + """>
                <div class="row nice-padding">
                    <div class="left">
                        <div class="col header-title">
                            <h1""" + (' class="icon icon-"' if WAGTAIL_VERSION < (2, 10) else "") + """>Translations <span>Test page</span></h1>
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
