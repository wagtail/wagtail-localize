from django.dispatch import Signal

language_activated = Signal(providing_args=["locale"])
language_deactivated = Signal(providing_args=["locale"])
