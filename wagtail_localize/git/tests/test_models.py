from django.test import TestCase
from wagtail.core.models import Page, Site
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file
from wagtail.documents.models import Document

from wagtail_localize.models import TranslationSource
from wagtail_localize.test.models import TestPage, TestSnippet

from wagtail_localize.git.models import Resource


def create_test_page(**kwargs):
    parent = kwargs.pop("parent", None) or Page.objects.get(id=1)
    page = parent.add_child(instance=TestPage(**kwargs))
    revision = page.save_revision()
    revision.publish()
    source, created = TranslationSource.get_or_create_from_instance(page)
    return page, source


class TestResource(TestCase):
    def test_get_for_object(self):
        # Set up a test translation
        page, source = create_test_page(
            title="Test page",
            slug="test-page",
            test_charfield="Some test translatable content",
        )

        resource = Resource.get_for_object(source.object)

        self.assertEqual(resource.object, source.object)
        self.assertEqual(resource.path, 'pages/test-page')

    def test_get_path_for_page(self):
        page, source = create_test_page(
            title="Test page",
            slug="test-page",
        )

        child_page, source = create_test_page(
            title="Child page",
            slug="child-page",
            parent=page,
        )

        self.assertEqual(Resource.get_path(page), 'pages/test-page')
        self.assertEqual(Resource.get_path(child_page), 'pages/test-page/child-page')

    def test_get_path_for_snippet(self):
        snippet = TestSnippet.objects.create(field="Foo")
        self.assertEqual(Resource.get_path(snippet), 'snippets/wagtail_localize_test.TestSnippet/1-testsnippet-object-1')

    def test_get_path_for_image(self):
        image = Image.objects.create(
            title="Test image",
            file=get_test_image_file(),
        )
        self.assertEqual(Resource.get_path(image), 'images/1-test-image')

    def test_get_path_for_document(self):
        doc = Document.objects.create(title="Test document")
        self.assertEqual(Resource.get_path(doc), 'documents/1-test-document')

    def test_get_path_for_other_model(self):
        site = Site.objects.get()
        self.assertEqual(Resource.get_path(site), 'other/wagtailcore.Site/1-localhost-default')
