from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.core.fields import StreamField
from wagtail.core.models import TranslatableMixin


class BaseTranslatableField:
    def __init__(self, field_name):
        self.field_name = field_name

    def get_field(self, model):
        return model._meta.get_field(self.field_name)

    def get_value(self, obj):
        return self.get_field(obj.__class__).value_from_object(obj)

    def is_editable(self, obj):
        """
        Returns True if the field is editable on the given object
        """
        return True

    def is_translated(self, obj):
        """
        Returns True if the value of this field on the given object should be
        extracted and submitted for translation
        """
        return False

    def is_synchronized(self, obj):
        """
        Returns True if the value of this field on the given object should be
        copied when translations are created/updated
        """
        return False


class TranslatableField(BaseTranslatableField):
    """
    A field that should be translated whenever the original page changes
    """

    def is_translated(self, obj):
        return True

    def is_synchronized(self, obj):
        field = self.get_field(obj.__class__)

        # Child relations should all be synchronised before translation
        if isinstance(field, (models.ManyToOneRel)) and isinstance(field.remote_field, ParentalKey):
            return True

        # Streamfields need to be re-synchronised before translation so the structure and non-translatable content is copied over
        return isinstance(field, StreamField)


class SynchronizedField(BaseTranslatableField):
    """
    A field that should always be kept in sync with the original page
    """

    def is_synchronized(self, obj):
        return self.is_editable(obj)


def copy_synchronised_fields(source, target):
    """
    Copies data in synchronised fields from the source object to the target object.
    """
    for translatable_field in getattr(source, 'translatable_fields', []):
        if translatable_field.is_synchronized(source):
            field = translatable_field.get_field(target.__class__)

            if isinstance(field, (models.ManyToOneRel)) and isinstance(field.remote_field, ParentalKey):
                # Use modelcluster's copy_child_relation for child relations

                if issubclass(field.related_model, TranslatableMixin):
                    # Get a list of the primary keys for the existing child objects
                    existing_pks_by_translation_key = {
                        child_object.translation_key: child_object.pk
                        for child_object in getattr(target, field.name).all()
                    }

                    # Copy the new child objects across (note this replaces existing ones)
                    child_object_map = source.copy_child_relation(field.name, target)

                    # Update locale of each child object and recycle PK
                    for (child_relation, source_pk), child_objects in child_object_map.items():
                        if source_pk is None:
                            # This is a list of the child objects that were never saved
                            for child_object in child_objects:
                                child_object.pk = existing_pks_by_translation_key.get(child_object.translation_key)
                                child_object.locale = target.locale
                        else:
                            child_object = child_objects

                            child_object.pk = existing_pks_by_translation_key.get(child_object.translation_key)
                            child_object.locale = target.locale

                else:
                    source.copy_child_relation(field.name, target)

            else:
                # For all other fields, just set the attribute
                setattr(
                    target, field.attname, getattr(source, field.attname)
                )
