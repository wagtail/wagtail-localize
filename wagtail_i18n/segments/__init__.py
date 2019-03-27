class SegmentValue:
    def __init__(self, path, text, format='plain'):
        self.path = path
        self.text = text
        self.format = format

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

        return SegmentValue(new_path, self.text, format=self.format)

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
        return base_path, SegmentValue(new_path, self.text, format=self.format)

    def __eq__(self, other):
        return isinstance(other, SegmentValue) and self.path == other.path and self.text == other.text and self.format == other.format

    def __repr__(self):
        return f'<SegmentValue {self.path} "{self.text}">'
