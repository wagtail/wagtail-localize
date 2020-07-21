class BaseMachineTranslator:
    display_name = "Unknown"

    def __init__(self, options):
        self.options = options

    def translate(self, strings):
        raise NotImplementedError

    def can_translate(self, source_locale, target_locale):
        return False
