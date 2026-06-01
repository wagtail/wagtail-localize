import contextlib

from .base import *  # noqa: F403


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-s29(yxq@%u+&l5!4gqn(u$&bp_^ncsp&@sl2dr+-h_+^s(g7@2"  # noqa: S105

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


with contextlib.suppress(ImportError):
    from .local import *  # noqa: F403
