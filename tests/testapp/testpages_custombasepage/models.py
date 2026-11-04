from tests.testapp.basepage.models import BasePage
from tests.testapp.pages import (
    PageWithCustomEditHandlerAbstract,
    TestGenerateTranslatableFieldsPageAbstract,
    TestHomePageAbstract,
    TestOverrideTranslatableFieldsPageAbstract,
    TestPageAbstract,
    TestWithTranslationModeDisabledPageAbstract,
    TestWithTranslationModeEnabledPageAbstract,
)


class TestPage(TestPageAbstract, BasePage):
    content_panels = BasePage.content_panels + TestPageAbstract.content_panels

    class Meta:
        abstract = False


class TestGenerateTranslatableFieldsPage(
    TestGenerateTranslatableFieldsPageAbstract, BasePage
):
    class Meta:
        abstract = False


class TestOverrideTranslatableFieldsPage(
    TestOverrideTranslatableFieldsPageAbstract, TestGenerateTranslatableFieldsPage
):
    class Meta:
        abstract = False


class TestHomePage(TestHomePageAbstract, BasePage):
    class Meta:
        abstract = False


class TestWithTranslationModeDisabledPage(
    TestWithTranslationModeDisabledPageAbstract, BasePage
):
    class Meta:
        abstract = False


class TestWithTranslationModeEnabledPage(
    TestWithTranslationModeEnabledPageAbstract, BasePage
):
    class Meta:
        abstract = False


class PageWithCustomEditHandler(PageWithCustomEditHandlerAbstract, BasePage):
    class Meta:
        abstract = False
