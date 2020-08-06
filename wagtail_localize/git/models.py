from django.db import models
from django.utils.text import slugify
from wagtail.core.models import Page, Locale
from wagtail.snippets.models import get_snippet_models
from wagtail.images.models import AbstractImage
from wagtail.documents.models import AbstractDocument

from wagtail_localize.models import TranslatableObject


class Resource(models.Model):
    """
    An object that is pushed to the git repo.
    """
    object = models.OneToOneField(TranslatableObject, on_delete=models.CASCADE, related_name='git_resource')

    # We need to save the path so that it doesn't change when pages are moved.
    path = models.TextField(unique=True)

    class Meta:
        ordering = ['path']

    @classmethod
    def get_for_object(cls, object):
        try:
            return cls.objects.get(object=object)

        except cls.DoesNotExist:
            # Raises exception if doesn't exist (let it crash!)
            instance = object.get_instance(Locale.get_default())

            return cls.objects.create(
                object=object,

                # TODO: How to deal with duplicate paths?
                path=cls.get_path(instance),
            )

    @classmethod
    def get_path(cls, instance):
        if isinstance(instance, Page):
            # Page paths have the format: `pages/URL_PATH`
            # Note: Page.url_path always starts with a '/'
            return 'pages' + instance.url_path.rstrip('/')

        else:
            model_name = instance._meta.app_label + '.' + instance.__class__.__name__

            if isinstance(instance, tuple(get_snippet_models())):
                # Snippet paths have the format `snippets/app_label.ModelName/ID-title-slugified`
                base_path = 'snippets/' + model_name

            elif isinstance(instance, AbstractImage):
                # Image paths have the format `images/ID-title-slugified`
                base_path = 'images'

            elif isinstance(instance, AbstractDocument):
                # Document paths have the format `documents/ID-title-slugified`
                base_path = 'documents'

            else:
                # All other models paths have the format `other/app_label.ModelName/ID-title-slugified`
                base_path = 'other/' + model_name

            return base_path + '/' + str(instance.pk) + '-' + slugify(str(instance))


class SyncLog(models.Model):
    """
    Logs whenever we push or pull.
    """
    ACTION_PUSH = 1
    ACTION_PULL = 2

    ACTION_CHOICES = [(ACTION_PUSH, "Push"), (ACTION_PULL, "Pull")]

    action = models.PositiveIntegerField(choices=ACTION_CHOICES)
    time = models.DateTimeField(auto_now_add=True)
    commit_id = models.CharField(max_length=40, blank=True)

    def add_translation(self, translation):
        SyncLogResource.objects.create(
            log=self,
            resource=Resource.get_for_object(translation.source.object),
            locale_id=translation.target_locale_id,
            source_id=translation.source_id,
        )

    class Meta:
        ordering = ['time']


class SyncLogResourceQuerySet(models.QuerySet):
    def unique_resources(self):
        return Resource.objects.filter(
            object_id__in=self.values_list("resource__object_id", flat=True)
        )

    def unique_locales(self):
        return Locale.objects.filter(id__in=self.values_list("locale_id", flat=True))


class SyncLogResource(models.Model):
    """
    Logs each resource that was transferred in a push/pull
    """
    log = models.ForeignKey(
        SyncLog, on_delete=models.CASCADE, related_name="resources"
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="logs"
    )

    # Null if pushing this resource, otherwise set to the locale being pulled
    locale = models.ForeignKey(
        "wagtailcore.Locale",
        null=True,
        on_delete=models.CASCADE,
        related_name="+",
    )

    # The source that was active at the time this resource was pushed/pulled
    source = models.ForeignKey(
        "wagtail_localize.TranslationSource",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SyncLogResourceQuerySet.as_manager()

    class Meta:
        ordering = ['log__time', 'resource__path']
