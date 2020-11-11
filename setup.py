#!/usr/bin/env python

from os import path

from setuptools import find_packages, setup

from wagtail_localize import __version__


# Hack to prevent "TypeError: 'NoneType' object is not callable" error
# in multiprocessing/util.py _exit_function when setup.py exits
# (see http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
try:
    import multiprocessing
except ImportError:
    pass

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="wagtail-localize",
    version=__version__,
    description="Translation plugin for Wagtail CMS",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Karl Hobley",
    author_email="karl@kaed.uk",
    url="",
    packages=find_packages(),
    include_package_data=True,
    license="BSD",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Framework :: Wagtail :: 2",
    ],
    install_requires=["Django>=2.2,<3.2", "Wagtail>=2.11,<2.12", "polib>=1.1,<2.0"],
    extras_require={
        "testing": ["dj-database-url==0.5.0", "freezegun==0.3.15"],
    },
    zip_safe=False,
)
