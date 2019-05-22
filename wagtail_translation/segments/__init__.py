class SegmentValue:
    def __init__(self, path, text):
        self.path = path
        self.text = text

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = SegmentValue('field', "The text")
        >>> s.wrap('relation')
        SegmentValue('relation.field', "The text")
        """
        new_path = base_path

        if self.path:
            new_path += '.' + self.path

        return SegmentValue(new_path, self.text)

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = SegmentValue('relation.field', "The text")
        >>> s.unwrap()
        'relation', SegmentValue('field', "The text")
        """
        base_path, *remaining_components = self.path.split('.')
        new_path = '.'.join(remaining_components)
        return base_path, SegmentValue(new_path, self.text)

    def is_empty(self):
        return self.text in ['', None]

    def __eq__(self, other):
        return isinstance(other, SegmentValue) and self.path == other.path and self.text == other.text

    def __repr__(self):
        return f'<SegmentValue {self.path} "{self.text}">'


class TemplateValue:
    def __init__(self, path, format, template, segment_count):
        self.path = path
        self.format = format
        self.template = template
        self.segment_count = segment_count

    def wrap(self, base_path):
        """
        Appends a component to the beginning of the path.

        For example:

        >>> s = TemplateValue('field', 'html', "<text position=\"0\">, 1)
        >>> s.wrap('relation')
        TemplateValue('relation.field', 'html', "<text position=\"0\">, 1)
        """
        new_path = base_path

        if self.path:
            new_path += '.' + self.path

        return TemplateValue(new_path, self.format, self.template, self.segment_count)

    def unwrap(self):
        """
        Pops a component from the beginning of the path. Reversing .wrap().

        For example:

        >>> s = TemplateValue('relation.field', 'html', "<text position=\"0\">, 1)
        >>> s.unwrap()
        'relation', TemplateValue('field', 'html', "<text position=\"0\">, 1)
        """
        base_path, *remaining_components = self.path.split('.')
        new_path = '.'.join(remaining_components)
        return base_path, TemplateValue(new_path, self.format, self.template, self.segment_count)

    def is_empty(self):
        return self.template in ['', None]

    def __eq__(self, other):
        return isinstance(other, TemplateValue) and self.path == other.path and self.format == other.format and self.template == other.template and self.segment_count == other.segment_count

    def __repr__(self):
        return f'<TemplateValue {self.path} format:{self.format} {self.segment_count} segments>'
