from django.contrib.admin.utils import quote
from django.urls import reverse
from rest_framework import fields, serializers, viewsets
from wagtail.snippets.views.snippets import get_snippet_model_from_url_params


class BaseSnippetSerializer(serializers.ModelSerializer):
    id = fields.ReadOnlyField(source="pk")
    title = fields.SerializerMethodField()
    edit_url = fields.SerializerMethodField()

    def get_title(self, instance):
        return str(instance)

    def get_edit_url(self, instance):
        return reverse(
            "wagtailsnippets:edit",
            args=[
                instance._meta.app_label,
                instance._meta.model_name,
                quote(instance.id),
            ],
        )


class SnippetViewSet(viewsets.ModelViewSet):
    def get_model(self):
        return get_snippet_model_from_url_params(
            self.kwargs["app_label"], self.kwargs["model_name"]
        )

    def get_queryset(self):
        return self.get_model()._default_manager.all()

    def get_serializer_class(self):
        model = self.get_model()

        return type(
            model.__name__ + "Serializer",
            (BaseSnippetSerializer,),
            {
                "Meta": type(
                    "Meta",
                    (object,),
                    {"model": model, "fields": ["id", "title", "edit_url"]},
                ),
            },
        )
