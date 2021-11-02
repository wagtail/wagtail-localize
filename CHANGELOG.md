# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2021-11-02

### Added

- [Add a means to disable the default translation mode](https://github.com/wagtail/wagtail-localize/pull/473) (@zerolab, sponsored by Instrument)
- [Add pre-commit support and lint using black](https://github.com/wagtail/wagtail-localize/pull/477)(@zerolab)

### Fixed

- [Handle configurable comments relation (Wagtail 2.15 fix)](https://github.com/wagtail/wagtail-localize/pull/468) (@gasman)
- [Allow overriding chooser blocks defined in `StructBlock`s](https://github.com/wagtail/wagtail-localize/pull/480) (@zerolab)

## [1.0rc4] - 2021-09-17

### Fixed

- [Auto-create alias pages after page is completely saved](https://github.com/wagtail/wagtail-localize/pull/454)

## [1.0rc3] - 2021-08-03

### Added

- [Support for Wagtail 2.14](https://github.com/wagtail/wagtail-localize/pull/440)
- [`overridable` keyword argument for `SynchronizedField`](https://github.com/wagtail/wagtail-localize/pull/438)

### Fixed

- [Make sure field level validation runs when translating snippets](https://github.com/wagtail/wagtail-localize/pull/427)

[unreleased]: https://github.com/wagtail/wagtail-localize/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc4...v1.0.0
[1.0rc4]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc3...v1.0rc4
[1.0rc3]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc2...v1.0rc3
