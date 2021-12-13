from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel, get_all_child_relations
from treebeard.mp_tree import MP_Node
from wagtail.core.fields import RichTextField, StreamField
from wagtail.core.models import Page, TranslatableMixin


try:
    from wagtail.core.models import COMMENTS_RELATION_NAME
except ImportError:
    COMMENTS_RELATION_NAME = "comments"


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

    def is_overridable(self, obj):
        """
        Returns True if the value of this field can be overridden. This is only
        applicable to fields that are synchronized
        """
        return self.is_synchronized(obj)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.field_name == other.field_name


class TranslatableField(BaseTranslatableField):
    """
    A field that should be translated whenever the original page changes
    """

    def is_translated(self, obj):
        return True

    def is_synchronized(self, source):
        field = self.get_field(source.__class__)

        # Child relations should all be synchronised before translation
        if isinstance(field, models.ManyToOneRel) and isinstance(
            field.remote_field, ParentalKey
        ):
            return True

        # We have a text field that has been cleared so we should mark it as synchronised
        if (
            isinstance(field, (RichTextField, models.TextField, models.CharField))
            and getattr(source, field.attname) == ""
        ):
            return True

        # Streamfields need to be re-synchronised before translation so
        # the structure and non-translatable content is copied over
        return isinstance(field, StreamField)

    def __repr__(self):
        return f"<TranslatableField {self.field_name}>"


class SynchronizedField(BaseTranslatableField):
    """
    A field that should always be kept in sync with the original page.
    """

    def __init__(self, field_name, overridable=True):
        super().__init__(field_name)
        self.overridable = overridable

    def is_synchronized(self, obj):
        return self.is_editable(obj)

    def is_overridable(self, obj):
        return self.is_synchronized(obj) and self.overridable

    def __repr__(self):
        return f"<SynchronizedField {self.field_name}>"


def get_translatable_fields(model):
    """
    Derives a list of translatable fields from the given model class.

    Arguments:
        model (Model class): The model class to derive translatable fields from.

    Returns:
        list[TranslatableField or SynchronizedField]: A list of TranslatableField and SynchronizedFields that were
            derived from the model.

    """
    # Note: If you update this, please update "docs/concept/translatable-fields-autogen.md"
    if hasattr(model, "translatable_fields"):
        return model.translatable_fields

    translatable_fields = []

    for field in model._meta.get_fields():
        # Ignore automatically generated IDs
        if isinstance(field, models.AutoField):
            continue

        # Ignore non-editable fields
        if not field.editable:
            continue

        # Ignore many to many fields (not supported yet)
        # TODO: Add support for these
        if isinstance(field, models.ManyToManyField):
            continue

        # Ignore fields defined by MP_Node mixin
        if issubclass(model, MP_Node) and field.name in ["path", "depth", "numchild"]:
            continue

        # Ignore some editable fields defined on Page
        if issubclass(model, Page) and field.name in [
            "go_live_at",
            "expire_at",
            "first_published_at",
            "content_type",
            "owner",
        ]:
            continue

        # URL, Email and choices fields are an exception to the rule below.
        # Text fields are translatable, but these are synchronised.
        if (
            isinstance(field, (models.URLField, models.EmailField))
            or isinstance(field, models.CharField)
            and field.choices
        ):
            translatable_fields.append(SynchronizedField(field.name))

        # Translatable text fields should be translatable
        elif isinstance(
            field, (StreamField, RichTextField, models.TextField, models.CharField)
        ):
            translatable_fields.append(TranslatableField(field.name))

        # Foreign keys to translatable models should be translated. Others should be synchronised
        elif isinstance(field, models.ForeignKey):
            # Ignore if this is a link to a parent model
            if isinstance(field, ParentalKey):
                continue

            # Ignore parent links
            if (
                isinstance(field, models.OneToOneField)
                and field.remote_field.parent_link
            ):
                continue

            # All FKs to translatable models should be translatable.
            # With the exception of pages that are special because we can localize them at runtime easily.
            # TODO: Perhaps we need a special type for pages where it links to the translation if availabe,
            # but falls back to the source if it isn't translated yet?
            # Note: This exact same decision was made for page chooser blocks in segments/extract.py
            if issubclass(field.related_model, TranslatableMixin) and not issubclass(
                field.related_model, Page
            ):
                translatable_fields.append(TranslatableField(field.name))
            else:
                translatable_fields.append(SynchronizedField(field.name))

        # Fields that support extracting segments are translatable
        elif hasattr(field, "get_translatable_segments"):
            translatable_fields.append(TranslatableField(field.name))

        else:
            # Everything else is synchronised
            translatable_fields.append(SynchronizedField(field.name))

    # Add child relations for clusterable models
    if issubclass(model, ClusterableModel):
        for child_relation in get_all_child_relations(model):
            # Ignore comments
            if (
                issubclass(model, Page)
                and child_relation.name == COMMENTS_RELATION_NAME
            ):
                continue

            if issubclass(child_relation.related_model, TranslatableMixin):
                translatable_fields.append(TranslatableField(child_relation.name))
            else:
                translatable_fields.append(SynchronizedField(child_relation.name))

    # Combine with any overrides defined on the model
    override_translatable_fields = getattr(model, "override_translatable_fields", [])

    if override_translatable_fields:
        override_translatable_fields = {
            field.field_name: field for field in override_translatable_fields
        }

        combined_translatable_fields = []
        for field in translatable_fields:
            if field.field_name in override_translatable_fields:
                combined_translatable_fields.append(
                    override_translatable_fields.pop(field.field_name)
                )
            else:
                combined_translatable_fields.append(field)

        if override_translatable_fields:
            combined_translatable_fields.extend(override_translatable_fields.values())

        return combined_translatable_fields

    else:
        return translatable_fields


def copy_synchronised_fields(source, target):
    """
    Copies data in synchronised fields from the source instance to the target instance.

    Note: Both instances must have the same model class

    Arguments:
        source (Model): The source instance to copy data from.
        target (Model): The target instance to copy data to.
    """
    for translatable_field in get_translatable_fields(source.__class__):
        if translatable_field.is_synchronized(source):
            field = translatable_field.get_field(target.__class__)

            if isinstance(field, models.ManyToOneRel) and isinstance(
                field.remote_field, ParentalKey
            ):
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
                    for (
                        _child_relation,
                        source_pk,
                    ), child_objects in child_object_map.items():
                        if source_pk is None:
                            # This is a list of the child objects that were never saved
                            for child_object in child_objects:
                                child_object.pk = existing_pks_by_translation_key.get(
                                    child_object.translation_key
                                )
                                child_object.locale = target.locale
                        else:
                            child_object = child_objects

                            child_object.pk = existing_pks_by_translation_key.get(
                                child_object.translation_key
                            )
                            child_object.locale = target.locale

                else:
                    source.copy_child_relation(field.name, target)

            else:
                # For all other fields, just set the attribute
                setattr(target, field.attname, getattr(source, field.attname))
