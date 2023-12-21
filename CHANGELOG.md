# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.8beta1] - 2023-12-21

### Added

- [LibreTranslate](https://libretranslate.com/) machine translator support ([#753](https://github.com/wagtail/wagtail-localize/pull/753)) @drivard
- Official support for Django 5.0 (when using Wagtail 5.2.2+) ([#755](https://github.com/wagtail/wagtail-localize/pull/755) and [#747](https://github.com/wagtail/wagtail-localize/pull/747)) @ACK1D and @softquantum

### Changed

- Replace usages of assertFormError which is removed in Django 5 ([#754](https://github.com/wagtail/wagtail-localize/pull/754) @softquantum
- Switched to using Read The Docs for documentation

## [1.7] - 2023-11-15

### Added

- Provisional support for Wagtail 6 ([#742](<(https://github.com/wagtail/wagtail-localize/pull/742)>) @zerolab

### Changed

- Updated target language code for [DeepL](https://www.deepl.com/en/docs-api/translate-text/translate-text) ([#739](https://github.com/wagtail/wagtail-localize/pull/739)) @unreadableusername

## [1.7rc1] - 2023-11-07

### Added

- [Wagtail 5.2 compatibility](https://github.com/wagtail/wagtail-localize/pull/735) @zerolab with thanks to @aekong
- Information side panel for snippets

### Changed

- Moved the languages breadcrumb header strip out of React ([#735](https://github.com/wagtail/wagtail-localize/pull/735))

## [1.6] - 2023-10-01

### Fixed

- [`'DeferringManyRelatedManager' object is not iterable` error when declaring `ParentalManyToManyField` as `SynchronizedField`](https://github.com/wagtail/wagtail-localize/pull/564) @hpoul
- [non-Page model translation when `WAGTAILLOCALIZE_SYNC_LIVE_STATUS_ON_TRANSLATE = False`](https://github.com/wagtail/wagtail-localize/pull/726) @zerolab

### Changed

- [`TranslationSource.create_or_update_translation` will publish a translation revision post transaction commit](https://github.com/wagtail/wagtail-localize/pull/711) @Abdul-Dridi
- [The locale filter in the translations report is now a selector based on the defined languages](https://github.com/wagtail/wagtail-localize/pull/716) @jhonatan-lopes

## [1.5.2] - 2023-09-07

### Changed

- [Be more defensive with fetching schema version from Django migration records](https://github.com/wagtail/wagtail-localize/pull/712) @zerolab

## [1.5.1] - 2023-06-11

### Added

- [Support for Django 4.2](https://github.com/wagtail/wagtail-localize/pull/692) @kmtracey
- [Official Wagtail 5.0 support](https://github.com/wagtail/wagtail-localize/pull/699) @nickmoreton, @zerolab

### Changed

- [Updated prettier version and delegated linting to pre-commit](https://github.com/wagtail/wagtail-localize/pull/694) @PeteCoward
- [Updated documentation dependencies and fix build errors](https://github.com/wagtail/wagtail-localize/pull/700) @zerolab
- [Updated colour declarations for dark-mode compatibility](https://github.com/wagtail/wagtail-localize/pull/701) @spikennm, @zerolab

### Removed

- [Python 3.7, pre Wagtail 4.1 logic](https://github.com/wagtail/wagtail-localize/pull/699) @nickmoreton, @zerolab

## [1.5] - 2023-02-23

### Changed

- [Updated tests to include Wagtail 4.2](https://github.com/wagtail/wagtail-localize/pull/673) @katdom13

### Removed

- [Support for Wagtail < 4.1](https://github.com/wagtail/wagtail-localize/pull/673) @katdom13

## [1.4] - 2023-01-22

### Added

- Improve authentication options for GoogleCloudTranslator (https://github.com/wagtail/wagtail-localize/pull/645) @ababic
  See https://www.wagtail-localize.org/how-to/integrations/machine-translation/ for further details.
- Add setting to skip publication when live pages are submitted for translation (https://github.com/wagtail/wagtail-localize/pull/656) @mattlinares
  The setting is `WAGTAILLOCALIZE_SYNC_LIVE_STATUS_ON_TRANSLATE`, defaulting to `True`.

## [1.3.3] - 2022-11-29

### Fixed

- [Rename imageChosen, documentChosen to chosen](https://github.com/wagtail/wagtail-localize/pull/650) @spikenn

### Changed

- Bump flit to >= 3.8.0 and use glob pattern in exclude declaration (https://github.com/wagtail/wagtail-localize/pull/658) @chris48s

## [1.3.2] - 2022-11-04

### Fixed

- [Fix `wagtailcore.pagerevision` model name resolution error in migrations](https://github.com/wagtail/wagtail-localize/pull/643) @laymonage
  This is hopefully the last edge case for the Revision model change in Wagtail 4.0
- [Fix Wagtail 4.1 compatibility](https://github.com/wagtail/wagtail-localize/pull/646) @zerolab

## [1.3.1] - 2022-10-17

### Fixed

- [Fix widget extraction for choosers directly in a `ListBlock`](https://github.com/wagtail/wagtail-localize/pull/639) @spikenn

## [1.3] - 2022-10-15

### Added

- [flit for packaging](https://github.com/wagtail/wagtail-localize/pull/589) @engineervix @chris48s
- [Support for the DeepL free API endpoint](https://github.com/wagtail/wagtail-localize/pull/604) @ramiboutas and hat tip to @vladox
- [Support for Wagtail 4.0](https://github.com/wagtail/wagtail-localize/pull/613) @janbaykara, @zerolab, @gasman
  Including [#588](https://github.com/wagtail/wagtail-localize/pull/588)[#592](https://github.com/wagtail/wagtail-localize/pull/592),
  [#599](https://github.com/wagtail/wagtail-localize/pull/599), [#601](https://github.com/wagtail/wagtail-localize/pull/601),
  [#616](https://github.com/wagtail/wagtail-localize/pull/616), [#618](https://github.com/wagtail/wagtail-localize/issues/618),
  [#630](https://github.com/wagtail/wagtail-localize/pull/630)r
- [Clean up localize data on source/destination removal](https://github.com/wagtail/wagtail-localize/pull/622) @zerolab
  To preserve the old behaviour, set `WAGTAILLOCALIZE_DISABLE_ON_DELETE = True` in your settings file.
- [Buttons to the page header menu](https://github.com/wagtail/wagtail-localize/pull/628) @th3hamm0r

### Fixed

- [Guard against `ManyToOneRel` child field without help text or verbose name](https://github.com/wagtail/wagtail-localize/pull/620) @zerolab
- [Widget extraction for choosers in `StructBlock` in `ListBlock`](https://github.com/wagtail/wagtail-localize/pull/633) @zerolab

### Removed

- [Support for Wagtail < 2.15](https://github.com/wagtail/wagtail-localize/pull/617)

## [1.3alpha4] - 2022-09-22

### Fixed

- [Missing modal include on the edit translation page](https://github.com/wagtail/wagtail-localize/issues/618)

### Removed

- [Support for Wagtail < 2.15](https://github.com/wagtail/wagtail-localize/pull/617)

## [1.3alpha3] - 2022-09-20

### Fixed

- [Migration dependency](https://github.com/wagtail/wagtail-localize/pull/616). With thanks to @iscilyas for testing and reporting.

## [1.3alpha1] - 2022-09-19

### Added

- [Support for Wagtail 4.0](https://github.com/wagtail/wagtail-localize/pull/613) @janbaykara, @zerolab
  [#588](https://github.com/wagtail/wagtail-localize/pull/588), [#592](https://github.com/wagtail/wagtail-localize/pull/592),
  [#599](https://github.com/wagtail/wagtail-localize/pull/599), [#601](https://github.com/wagtail/wagtail-localize/pull/601) with extra thanks to @gasman
- [flit for packaging](https://github.com/wagtail/wagtail-localize/pull/589) @engineervix @chris48s
- [Support for the DeepL free API endpoint](https://github.com/wagtail/wagtail-localize/pull/604) @ramiboutas with hat/tip to @vladox

## [1.2.1] - 2022-06-05

### Fixed

- [Queryset filter to get translation source](https://github.com/wagtail/wagtail-localize/pull/578) @sheralim012
- (PageChooser widget extraction in `Orderable`s)[https://github.com/wagtail/wagtail-localize/pull/584] @zerolab
- (Fix duplicate locale definition in `TranslatableCreateView` template)[https://github.com/wagtail/wagtail-localize/pull/584] @benmth

### Changed

- [Improve docs for Google Cloud Translate](https://github.com/wagtail/wagtail-localize/pull/578) @chris48s
- [Update field configuration docs with note about `translatable_fields` support in `StructBlock`](https://github.com/wagtail/wagtail-localize/pull/582) @enzedonline

## [1.2] - 2022-05-20

### Added

- [Translatable ModelAdmin](https://github.com/wagtail/wagtail-localize/pull/550) @dinoperovic
- [Support for Wagtail 3.0](https://github.com/wagtail/wagtail-localize/pull/569) + Wagtail 3.0 PyPI trove classifier @zerolab
- [Add a mechanism for plugging in task queues](https://github.com/wagtail/wagtail-localize/pull/549) @kaedroho
- [Django 4.0 PyPI trove classifier](https://github.com/wagtail/wagtail-localize/pull/566) @lb-

### Fixed

- [Stop translations from being automatically published when source is in draft state](https://github.com/wagtail/wagtail-localize/pull/511) @AndrewCalderSpringload
- [Fix header styling for Wagtail 3.0](https://github.com/wagtail/wagtail-localize/pull/560) @kaedroho
- [Limit width of segment editor on wide screens](https://github.com/wagtail/wagtail-localize/pull/561) @kaedroho
- Compatibility with Wagtail 4.0 - [#557](https://github.com/wagtail/wagtail-localize/pull/557), [#572](https://github.com/wagtail/wagtail-localize/pull/572) @zerolab

## [1.1.1] - 2022-04-28

### Fixed

- [Fix `ListBlock` in `StrucBlock` in `ListBlock` in `StructBlock` and similar nesting](https://github.com/wagtail/wagtail-localize/pull/559) @zerolab

## [1.1.1] - 2022-03-25

### Fixed

- [Fix `ListBlock` segment extraction for empty lists](https://github.com/wagtail/wagtail-localize/pull/545) @mb03
- [Fix chooser handling in nested `StreamBlock`s](https://github.com/wagtail/wagtail-localize/pull/546) @zerolab, @kaedroho
  This is a follow up to [Allow overriding chooser blocks defined in `StructBlock`s](https://github.com/wagtail/wagtail-localize/pull/480)

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

[unreleased]: https://github.com/wagtail/wagtail-localize/compare/v1.7...HEAD
[1.8beta1]: https://github.com/wagtail/wagtail-localize/compare/v1.7...v1.8-beta.1
[1.7]: https://github.com/wagtail/wagtail-localize/compare/v1.7rc1...v1.7
[1.7rc1]: https://github.com/wagtail/wagtail-localize/compare/v1.6...v1.7rc1
[1.6]: https://github.com/wagtail/wagtail-localize/compare/v1.5.2...v1.6
[1.5.2]: https://github.com/wagtail/wagtail-localize/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/wagtail/wagtail-localize/compare/v1.5...v1.5.1
[1.5]: https://github.com/wagtail/wagtail-localize/compare/v1.4...v1.5
[1.4]: https://github.com/wagtail/wagtail-localize/compare/v1.3.3...v1.4
[1.3.2]: https://github.com/wagtail/wagtail-localize/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/wagtail/wagtail-localize/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/wagtail/wagtail-localize/compare/v1.3...v1.3.1
[1.3]: https://github.com/wagtail/wagtail-localize/compare/v1.3.0-alpha.3...v1.3
[1.3alpha1]: https://github.com/wagtail/wagtail-localize/compare/v1.3.0-alpha.1...v1.3.0-alpha.3
[1.3alpha1]: https://github.com/wagtail/wagtail-localize/compare/v1.2.1...v1.3.0-alpha.1
[1.2.1]: https://github.com/wagtail/wagtail-localize/compare/v1.2...v1.2.1
[1.2]: https://github.com/wagtail/wagtail-localize/compare/v1.1.2...v1.2
[1.1.2]: https://github.com/wagtail/wagtail-localize/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/wagtail/wagtail-localize/compare/v1.1...v1.1.1
[1.1]: https://github.com/wagtail/wagtail-localize/compare/v1.1rc2...v1.1
[1.1rc2]: https://github.com/wagtail/wagtail-localize/compare/v1.1rc1...v1.1rc2
[1.1rc1]: https://github.com/wagtail/wagtail-localize/compare/v1.0.1...v1.1rc1
[1.0.1]: https://github.com/wagtail/wagtail-localize/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc4...v1.0.0
[1.0rc4]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc3...v1.0rc4
[1.0rc3]: https://github.com/wagtail/wagtail-localize/compare/v1.0rc2...v1.0rc3
