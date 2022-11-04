from .version import get_version


# release must be one of alpha, beta, rc, or final
VERSION = (1, 3, 2, "final", 1)

__version__ = get_version(VERSION)
