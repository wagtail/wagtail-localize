#!/usr/bin/env python

from os import path

from setuptools import find_packages, setup


this_directory = path.abspath(path.dirname(__file__))

version = {}
with open(path.join(this_directory, "wagtail_localize", "version.py")) as f:
    exec(f.read(), version)

with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="wagtail-localize",
    version=version["__version__"],
    description="Translation plugin for Wagtail CMS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Karl Hobley",
    author_email="karl@torchbox.com",
    url="https://www.wagtail-localize.org",
    packages=find_packages(),
    include_package_data=True,
    license="BSD",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.2",
        "Framework :: Wagtail",
        "Framework :: Wagtail :: 2",
    ],
    install_requires=["Django>=2.2,<4.1", "Wagtail>=2.11,<2.17", "polib>=1.1,<2.0"],
    extras_require={
        "testing": ["dj-database-url==0.5.0", "freezegun==1.1.0"],
        "documentation": [
            "mkdocs==1.1.2",
            "mkdocs-material==6.2.8",
            "mkdocs-mermaid2-plugin==0.5.1",
            "mkdocstrings==0.14.0",
            "mkdocs-include-markdown-plugin==2.8.0",
        ],
    },
    zip_safe=False,
)
