from .version import get_version


# release must be one of alpha, beta, rc, or final
VERSION = (1, 9, 0, "final", 0)

__version__ = get_version(VERSION)
