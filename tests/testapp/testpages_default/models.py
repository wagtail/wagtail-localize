from wagtail.models import Page

from tests.testapp.pages import (
    PageWithCustomEditHandlerAbstract,
    TestGenerateTranslatableFieldsPageAbstract,
    TestHomePageAbstract,
    TestOverrideTranslatableFieldsPageAbstract,
    TestPageAbstract,
    TestWithTranslationModeDisabledPageAbstract,
    TestWithTranslationModeEnabledPageAbstract,
)


class TestPage(TestPageAbstract, Page):
    content_panels = Page.content_panels + TestPageAbstract.content_panels


class TestGenerateTranslatableFieldsPage(
    TestGenerateTranslatableFieldsPageAbstract, Page
):
    pass


class TestOverrideTranslatableFieldsPage(
    TestOverrideTranslatableFieldsPageAbstract, TestGenerateTranslatableFieldsPage
):
    pass


class TestHomePage(TestHomePageAbstract, Page):
    pass


class TestWithTranslationModeDisabledPage(
    TestWithTranslationModeDisabledPageAbstract, Page
):
    pass


class TestWithTranslationModeEnabledPage(
    TestWithTranslationModeEnabledPageAbstract, Page
):
    pass


class PageWithCustomEditHandler(PageWithCustomEditHandlerAbstract, Page):
    pass
