from wagtail.models import AbstractPage


class BasePage(AbstractPage):
    """This is a custom base page model that is used in the tests to ensure that
    wagtail-localize works with custom base page models."""
