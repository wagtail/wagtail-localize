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

    def is_synchronized(self, obj):
        """
        Returns True if the value of this field on the given object should be
        pushed to other translations.
        """
        return False


class TranslatableField(BaseTranslatableField):
    """
    A field that should be translated whenever the original page changes
    """

    def is_editable(self, obj):
        return obj.is_source_translation


class SynchronizedField(BaseTranslatableField):
    """
    A field that should always be kept in sync with the original page
    """

    def is_editable(self, obj):
        return obj.is_source_translation

    def is_synchronized(self, obj):
        return self.is_editable(obj)
