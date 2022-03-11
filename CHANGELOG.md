# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1] - 2022-03-11

### Added

- [Delete the related Translation object when converting a page back to alias](https://github.com/wagtail/wagtail-localize/pull/532) @zerolab
  This is the follow up to [Ability to convert back to alias](https://github.com/wagtail/wagtail-localize/pull/515)

### Fixed

- [Various failures against the latest Wagtail `main` branch](https://github.com/wagtail/wagtail-localize/pull/536) @zerolab

## [1.1rc2] - 2022-03-04

### Added

- [Support for `ListBlock`s nested in `StructBlock`s](https://github.com/wagtail/wagtail-localize/pull/525)

### Fixed

- CSRF token in `convertToAliasAction` (@zerolab)
- Missing updated compiled messages
- Typos in installation instructions (@th3hamm0r) and templates tutorial (@Redjam)

## [1.1rc1] - 2022-02-22

### Added

- [Support for Wagtail 2.16 and Django 4.0](https://github.com/wagtail/wagtail-localize/pull/509) (@zerolab)
- [Support for ListBlock](https://github.com/wagtail/wagtail-localize/pull/510) (@zerolab)
  Note: this only works with Wagtail 2.16+ and blocks that been resaved with it.
- [Ability to convert back to alias](https://github.com/wagtail/wagtail-localize/pull/515) (@zerolab)
- [Sync source page privacy settings with translated page](https://github.com/wagtail/wagtail-localize/pull/496) (@zerolab)

### Fixed

- [Clear text fields on sync](https://github.com/wagtail/wagtail-localize/pull/495) (@zerolab)
- [Reset the `has_error` flag on po import](https://github.com/wagtail/wagtail-localize/pull/507) (@zerolab)
- [`edit_string_translation` and `edit_override` views when DRF is configured with explicit permission/authentication classes](https://github.com/wagtail/wagtail-localize/pull/513) (@bmihelac, @zerolab)

### Changed

- [Redirect to newly translate page's edit view when submitting a translation for a single locale](https://github.com/wagtail/wagtail-localize/pull/518) (@mixxorz)

## [1.0.1] - 2021-12-01

### Added

- [Add mechanism for new form components in the submit/update translation views](https://github.com/wagtail/wagtail-localize/pull/491) (@zerolab, sponsored by Twilio)

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

[unreleased]: https://github.com/wagtail/wagtail-localize/compare/v1.1...HEAD
[1.1]: https://github.com/wagtail/wagtail-localize/compare/v1.1rc2...v1.1
[1.1rc2]: https://github.com/wagtail/wagtail-localize/compare/v1.1rc1...v1.1rc2
[1.1rc1]: https://github.com/wagtail/wagtail-localize/compare/v1.0.1...v1.1rc1
[1.0.1]: https://github.com/wagtail/wagtail-localize/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc4...v1.0.0
[1.0rc4]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc3...v1.0rc4
[1.0rc3]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc2...v1.0rc3
