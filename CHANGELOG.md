# CHANGELOG

<!-- version list -->

## v31.1.0 (2026-03-22)

### Bug Fixes

- `mcq see` with no argument raised an error.
  ([`2221ef0`](https://github.com/wxgeo/ptyx-mcq/commit/2221ef05d3d7413924adc72708f4382906ea1218))

- Regression fixed (text artefact when smallgraphlib was imported)
  ([`9d48683`](https://github.com/wxgeo/ptyx-mcq/commit/9d48683eb22252fcbc0478618a3f62098553cc2e))

- Several small bugs.
  ([`250c394`](https://github.com/wxgeo/ptyx-mcq/commit/250c394e3c225764676d3d0149fd0629fed45030))

- Support for new ptyx version.
  ([`32c9df8`](https://github.com/wxgeo/ptyx-mcq/commit/32c9df8a15412b5e5542d4237b214a919d98c35d))

- The table in scores.xlsx was not correctly displayed.
  ([`d8d3c4e`](https://github.com/wxgeo/ptyx-mcq/commit/d8d3c4e23d0b196d61b6d52d9a4bbc995e82ec77))

### Features

- Add :LATEX-PACKAGES: and :LATEX-HEADER: directives.
  ([`3c557c5`](https://github.com/wxgeo/ptyx-mcq/commit/3c557c5d221518b96b284a566f40fead135c9126))

- Add the students IDs in the generated CSV and XLSX scores' files.
  ([`5f239cb`](https://github.com/wxgeo/ptyx-mcq/commit/5f239cbebf8906b1a11b96355a8e55cad09bec63))

- Enables shell completion when the application is installed in a virtual env.
  ([`cdb3112`](https://github.com/wxgeo/ptyx-mcq/commit/cdb3112d2be2eb3d9a21f7d0454c6c582af364e3))


## v31.0.1 (2025-11-04)

### Bug Fixes

- Incorrect import in a module.
  ([`caf7a19`](https://github.com/wxgeo/ptyx-mcq/commit/caf7a19f13f69db7bdbebd9537534be998dda444))


## v31.0.0 (2025-10-30)

### Bug Fixes

- `mcq see` is working again.
  ([`4857971`](https://github.com/wxgeo/ptyx-mcq/commit/4857971636464d484c75523da689651615ad9ff5))

- Do not append stats to CSV files.
  ([`936e3af`](https://github.com/wxgeo/ptyx-mcq/commit/936e3af0986e103e4450d1b19a91e247eafecdf4))

- Remove trailing spaces in header config keys.
  ([`9c8c079`](https://github.com/wxgeo/ptyx-mcq/commit/9c8c079711a5ebd70667bc2ce6308cafd1d6780f))

- Support smallgraphlib 0.10.0
  ([`baca175`](https://github.com/wxgeo/ptyx-mcq/commit/baca175a940b150d66607f35b92b9c13d3a8215e))

### Features

- Add `--version` in CLI.
  ([`f6d1d4b`](https://github.com/wxgeo/ptyx-mcq/commit/f6d1d4b5974508b4c344d3bb587ebc355782ffaf))

- Add a chart to illustrate scores distribution.
  ([`d76677b`](https://github.com/wxgeo/ptyx-mcq/commit/d76677bbf108ee39880024dd6f140406de2e881b))

- Append some statistics at the end of the generated `scores.xlsx` file.
  ([`ea29685`](https://github.com/wxgeo/ptyx-mcq/commit/ea2968545ffaf5c159f262af1d277847cf15755c))

- Better error messages when reading an unknown document ID.
  ([`0a49cf0`](https://github.com/wxgeo/ptyx-mcq/commit/0a49cf093ec122aa09c843b845279bdfd65a16a6))

- Implement the new +* and -* commands when editing answers.
  ([`845f31c`](https://github.com/wxgeo/ptyx-mcq/commit/845f31cc948885af63c4cbbfa4e6e2bbafe34a3b))

- Logo.svg
  ([`9f5d002`](https://github.com/wxgeo/ptyx-mcq/commit/9f5d0029248b9b540398218c6fa7dd83e59bf234))

- Reset context between each question version.
  ([`c1a8d88`](https://github.com/wxgeo/ptyx-mcq/commit/c1a8d88096f36af6abff8008525d7f3d758b6d81))

- Use new traceback feature from ptyx 29.2+ to display more accurate debug information.
  ([`9fb3dc2`](https://github.com/wxgeo/ptyx-mcq/commit/9fb3dc282ee0da26d907b2d19acf6fc8d9aa9552))

### Refactoring

- Adapt code to ptyx refactoring.
  ([`9ad4a82`](https://github.com/wxgeo/ptyx-mcq/commit/9ad4a82aac7a46d7d3ec564f797b7bf81dd66fdc))

### Testing

- Make tests compatible with ptyx commit #eb5a33885a6af8d
  ([`7009c32`](https://github.com/wxgeo/ptyx-mcq/commit/7009c3242a20591295c7e397996018bf8ef4eac7))


## v30.0.0 (2025-01-08)

### Bug Fixes

- Add (again) ability to skip documents... This major new version is almost complete now.
  ([`b1d98ca`](https://github.com/wxgeo/ptyx-mcq/commit/b1d98caf5334a92034c9d58319d0f9f9a8231ad0))

- Create parent directory before creating a .skip file.
  ([`d239141`](https://github.com/wxgeo/ptyx-mcq/commit/d2391415309417b5c2a4ecba0a03eb1b1b5ffa32))

- Final pdf files were not generated anymore. Add a test for this.
  ([`d880bf4`](https://github.com/wxgeo/ptyx-mcq/commit/d880bf45165652340e7a64933c74469cdb0d32d1))

- Fix major regression (image was not rotated anymore during the calibration process!)
  ([`ef9ddfe`](https://github.com/wxgeo/ptyx-mcq/commit/ef9ddfe33da566192f71be44eb5ecb69a0dd5bea))

- Fix several bugs in conflict handler.
  ([`cd221ef`](https://github.com/wxgeo/ptyx-mcq/commit/cd221efe762872e1cb6f52cec0138b5cb925da03))

### Features

- Improve messages in integrity checker.
  ([`efabd19`](https://github.com/wxgeo/ptyx-mcq/commit/efabd19fba429a632c32421d824b1971eaa1af44))

- Improve the error message when there are duplicate answers.
  ([`a5a37c3`](https://github.com/wxgeo/ptyx-mcq/commit/a5a37c330b04865e04b619b9fbbd8fd0130dbb2a))

### Refactoring

- Document.pictures -> Document.all_pictures.
  ([`2d2e7cf`](https://github.com/wxgeo/ptyx-mcq/commit/2d2e7cfdfc215d1b39b5a9917f75e3ebaf0be27a))

- Refactor CLI.
  ([`b0450df`](https://github.com/wxgeo/ptyx-mcq/commit/b0450dfadae00a87d7814ec005131344599648ea))

- Update and simplify dependencies.
  ([`8e98bcb`](https://github.com/wxgeo/ptyx-mcq/commit/8e98bcb93624665e4a8ef038a7d256cf2744a1f3))

### Testing

- Fix 3 remaining tests. All but one test pass now.
  ([`40c06c0`](https://github.com/wxgeo/ptyx-mcq/commit/40c06c08367245c7d7ede826a728ed533ef1474d))

- Fix failing test.
  ([`20deb9f`](https://github.com/wxgeo/ptyx-mcq/commit/20deb9f01ac3ce38b20732c20971485db971792a))

- Fix last remaining test.
  ([`f7cfeb9`](https://github.com/wxgeo/ptyx-mcq/commit/f7cfeb9468316f98cbd37774032dca3405cdb898))

- Remove old tests data.
  ([`d7c9d86`](https://github.com/wxgeo/ptyx-mcq/commit/d7c9d86dd2a5c03dc0ec0819d61cb64163ed400e))


## v28.0.0 (2024-11-05)

### Bug Fixes

- Display help for the specified `mcq` subcommand, not for `mcq` in general.
  ([`d84904a`](https://github.com/wxgeo/ptyx-mcq/commit/d84904ad9c27a84dfeeb459c3bab397f9c27e147))

### Refactoring

- Move templates directory.
  ([`7d55079`](https://github.com/wxgeo/ptyx-mcq/commit/7d55079ad18bb937a5c7f56f2a956af2c382c728))


## v27.4.0 (2024-11-05)

### Bug Fixes

- After last refactoring, missing names were counted as duplicates as well.
  ([`f46bcdc`](https://github.com/wxgeo/ptyx-mcq/commit/f46bcdcad8d400074e8d0706a7b7c5e2f4974196))

- Fix issue if os.cpu_count() return None.
  ([`6aac001`](https://github.com/wxgeo/ptyx-mcq/commit/6aac0016678807dac4ae125e61300e7129fedb3d))

- Fix small issue when searching for a file with a composite extension.
  ([`82a5cdf`](https://github.com/wxgeo/ptyx-mcq/commit/82a5cdf5508874c9acdcb8376be03d596cfcc90f))

- Fix some corner cases for names conflict (when user entered name induces other conflicts).
  ([`a57c984`](https://github.com/wxgeo/ptyx-mcq/commit/a57c9841751a7ffdd993cd0c38dbdcc3891c90f4))

- Only call sys.exit() at outer lever when searching for a ptyx file.
  ([`eb26350`](https://github.com/wxgeo/ptyx-mcq/commit/eb263504842d589700e4433a80b80e0bf7f6a8fa))

- Remove all sys.exit() calls except from main script.
  ([`5d513bf`](https://github.com/wxgeo/ptyx-mcq/commit/5d513bfb570be4a60b38d5229d891cf4bbbb8c9e))

### Features

- Add `mcq doc <subcommand>`, and remove old `mcq strategies` command.
  ([`fecd9fa`](https://github.com/wxgeo/ptyx-mcq/commit/fecd9fa075b2e8b5145de04c29c2a32e4aebdb09))

- Autodetect .ptyx files with wrong filename's extension.
  ([`5b37a3e`](https://github.com/wxgeo/ptyx-mcq/commit/5b37a3e86a5febc50287d8f72a8c11705fde458d))

- Implement `mcq see <StudentName>` to display student pdf.
  ([`9e67353`](https://github.com/wxgeo/ptyx-mcq/commit/9e67353bdc196d0afb67cbe7472fb4dfb11afa64))

- Make config files extension a parameter.
  ([`6c22490`](https://github.com/wxgeo/ptyx-mcq/commit/6c22490092c17008dbeb7573d085fb7e8767793a))

- Much better multiprocessing usage, reducing memory consumption.
  ([`44cd54c`](https://github.com/wxgeo/ptyx-mcq/commit/44cd54c9d1f806edf79341c516e0f7363bf265a5))

- Multiprocessing scan - first draft.
  ([`d9162db`](https://github.com/wxgeo/ptyx-mcq/commit/d9162dbabaefad97af74ad0de058b17100a11165))

- Search again for student names from IDs when resolving conflicts, in case config changed.
  ([`0c29668`](https://github.com/wxgeo/ptyx-mcq/commit/0c296682ee3a0e751dae686eed09c19953d0c581))

- Support smallgraphlib 0.10.
  ([`dfc4704`](https://github.com/wxgeo/ptyx-mcq/commit/dfc4704928af5be75682d6077f641a39c22ef8b5))

- Use multiprocessing to analyze checkboxes too.
  ([`a9867c7`](https://github.com/wxgeo/ptyx-mcq/commit/a9867c732971fbdbbf0ae0b702f8c6f73ce3cae6))

- Write `ok` to validate name suggestion.
  ([`8d3930d`](https://github.com/wxgeo/ptyx-mcq/commit/8d3930dd6aaaff979ab1a86992016edd52e7e132))

### Refactoring

- Add ability to customize AllDataIssuesFixer.
  ([`7c3c679`](https://github.com/wxgeo/ptyx-mcq/commit/7c3c67945abf969e9296db659db6813cfd3d5f1b))

- Add ability to customize AllDataIssuesFixer.
  ([`4c0394c`](https://github.com/wxgeo/ptyx-mcq/commit/4c0394c350f3b3382c4d0fca7e2841e6c5c05386))

- Create an abstract base class for conflict solver.
  ([`cf89408`](https://github.com/wxgeo/ptyx-mcq/commit/cf894087a26feee05de157ddaf85c98335ce5408))

- Create method `scan_page()`, to prepare for multiprocessing.
  ([`39f85c3`](https://github.com/wxgeo/ptyx-mcq/commit/39f85c322523d35a9d46b9e426725234bef6acd1))

- Create separate python files for scan issues' checkers and fixers.
  ([`b705f2f`](https://github.com/wxgeo/ptyx-mcq/commit/b705f2f70e0200a42502ee8a022e9345b6dc2525))

- Enable integrity issues' solver to be handled by an external GUI.
  ([`08a7397`](https://github.com/wxgeo/ptyx-mcq/commit/08a7397ae345fd5b0c5fb72d85a7dd2da615a1c3))

- Enable MCQ answers check to be handled by an external GUI.
  ([`01178a8`](https://github.com/wxgeo/ptyx-mcq/commit/01178a879c24eb1490b7785b85c8a79260ac8723))

- Enable names issues' solver to be handled by an external GUI.
  ([`73990cb`](https://github.com/wxgeo/ptyx-mcq/commit/73990cb6fb060fb395f318eac4fcfad56c26e99a))

- Major refactoring of conflict solver. This should make GUI creation much easier.
  ([`a666bbf`](https://github.com/wxgeo/ptyx-mcq/commit/a666bbf905d312c365cab36dca08ff196977fcb2))

- New class to handle checkboxes.
  ([`44cd54c`](https://github.com/wxgeo/ptyx-mcq/commit/44cd54c9d1f806edf79341c516e0f7363bf265a5))

- New small changes to prepare multiprocessing.
  ([`51a2091`](https://github.com/wxgeo/ptyx-mcq/commit/51a20913107c1e91513b86c9d5595002a120520c))

- Prepare the code to accept alternative (GUI) conflict solver.
  ([`55972e3`](https://github.com/wxgeo/ptyx-mcq/commit/55972e35afa984c61d9681c076d7ceb6fe9a94d4))

- Remove old code.
  ([`778bbd9`](https://github.com/wxgeo/ptyx-mcq/commit/778bbd94781455ea5e2110fe47602ff7675ca51d))

- Rename files with more explicit names.
  ([`f72a09e`](https://github.com/wxgeo/ptyx-mcq/commit/f72a09ed95cd4a8622f13c9e0f5d64d276b6f16a))

- Small refactoring.
  ([`3752a1d`](https://github.com/wxgeo/ptyx-mcq/commit/3752a1d23e72260abd7a5a79a0bc7edc0a3cd943))

### Testing

- Add tests for answers detection edition.
  ([`b9b8ec0`](https://github.com/wxgeo/ptyx-mcq/commit/b9b8ec0a11efc76f29a71e0d2ce7aae0c87ae8a3))

- Add tests to test_is_ptyx_file()
  ([`d236689`](https://github.com/wxgeo/ptyx-mcq/commit/d236689aeaf74946d9a6f4c3db82dad9cfb7405f))

- Fix failing test since commit 0c296682e.
  ([`1bbca26`](https://github.com/wxgeo/ptyx-mcq/commit/1bbca26031ce7ab4a106c1db530cf5b08c7e2035))

- Refactor tests concerning conflicts solver.
  ([`0751029`](https://github.com/wxgeo/ptyx-mcq/commit/0751029d81b303aed22b9e0c703dbcd5803ac20a))


## v27.3.0 (2024-04-22)

### Bug Fixes

- SameAnswerError is now compatible with pickle.
  ([`2f333e5`](https://github.com/wxgeo/ptyx-mcq/commit/2f333e54b192f5c851cbf02192e90ae17423657b))

### Features

- Add a method to easily update a configuration file.
  ([`ed2757d`](https://github.com/wxgeo/ptyx-mcq/commit/ed2757d98d55428f8506080a62c47da969e88fc9))

- Define DEFAULT_PTYX_MCQ_COMPILATION_OPTIONS global variable.
  ([`c553c40`](https://github.com/wxgeo/ptyx-mcq/commit/c553c40c0b49943d91be1d3a888b99e0f30ca12a))

- Disable PYTHONHASHSEED by default, to make compilations more reproducible.
  ([`79684ec`](https://github.com/wxgeo/ptyx-mcq/commit/79684ec9d2057d95c60f6cc3b34549464b56ac40))

- Disable PYTHONHASHSEED only when launching command.
  ([`ad31d50`](https://github.com/wxgeo/ptyx-mcq/commit/ad31d50f5dd9d8455cfff4ae76722eb209a73d37))

- In case of incorrect ID, propose the most similar existing one.
  ([`28f92a0`](https://github.com/wxgeo/ptyx-mcq/commit/28f92a0c1c3c7adacc418e5469e5b513a2d196e9))

- Support for new ptyx version.
  ([`6dfc5f1`](https://github.com/wxgeo/ptyx-mcq/commit/6dfc5f11531b03d52b0ba91e56161f28e4e8bdee))

- Use multiprocessing to generate amended pdf.
  ([`de0942d`](https://github.com/wxgeo/ptyx-mcq/commit/de0942d1823a44a2f0e310a3af911ca82d9474ba))


## v27.2.0 (2024-03-05)

### Bug Fixes

- Smallgraphlib support was broken in preview mode.
  ([`07a939d`](https://github.com/wxgeo/ptyx-mcq/commit/07a939db775c659de6b2f813c3be18bf9dc71cf9))

### Features

- Add an additional security layer against duplicate answers.
  ([`5c92733`](https://github.com/wxgeo/ptyx-mcq/commit/5c9273355ae2a9ce7affd5e7e58e2a738b2df58c))

- Protect `mcq make` from accidentally overwriting generated document.
  ([`eb74d58`](https://github.com/wxgeo/ptyx-mcq/commit/eb74d580e7c5ae72314126d4d31572ce91396b39))

### Refactoring

- Update code to match new ptyx version (28.2+).
  ([`c2d593d`](https://github.com/wxgeo/ptyx-mcq/commit/c2d593d34437eb123a9dc53f4a93caeb6443c7cd))


## v27.1.0 (2024-01-30)

### Features

- MCQ can now include special answers whose truth value depends on context.
  ([`4cf036d`](https://github.com/wxgeo/ptyx-mcq/commit/4cf036d4087d6a59e05a929aa055fc94ec271d0b))

- New context option to main make() function.
  ([`e582d97`](https://github.com/wxgeo/ptyx-mcq/commit/e582d97f76e74a36160b66c9d5a5f91f1006368f))


## v27.0.0 (2024-01-26)

### Bug Fixes

- @-directives must appear just before answers.
  ([`3d9ae54`](https://github.com/wxgeo/ptyx-mcq/commit/3d9ae54928ec22a522f3892e1b5cbd3ba14c6308))

- Fix bug in fitz colorspace names.
  ([`bbc980c`](https://github.com/wxgeo/ptyx-mcq/commit/bbc980c2f89237b274f75d3e46e94e1084486b53))

- Fix duplicate names conflict solver. Add tests.
  ([`786f7c9`](https://github.com/wxgeo/ptyx-mcq/commit/786f7c9d24da44e089590d0761650c5e8de90f79))

- Fix severe regression in scan calibration induced by previous refactoring.
  ([`8f3359f`](https://github.com/wxgeo/ptyx-mcq/commit/8f3359f21b2d7b912413e81479d1208e3221aebb))

- Nicer display for exercise preview mode.
  ([`322762b`](https://github.com/wxgeo/ptyx-mcq/commit/322762b2f86fe7349b272dab7e5793e531296c64))

- When runnning a scan again, don't ask for documents already skipped before.
  ([`3abf31b`](https://github.com/wxgeo/ptyx-mcq/commit/3abf31b078153efb58cfb68836dcd3ee645636bd))

### Features

- Add `add_directories()` function (CLI must yet be updated accordingly).
  ([`31939d1`](https://github.com/wxgeo/ptyx-mcq/commit/31939d14d54b5740e80e1994ae1f8394ca35e5c5))

- Add a useful warning when a lonely python block delimiter is found in an exercise.
  ([`dd8a99a`](https://github.com/wxgeo/ptyx-mcq/commit/dd8a99aea304c58651d7e116f961fb50c1ad2e77))

- Add preview mode, using `preview` latex package.
  ([`3ac1d99`](https://github.com/wxgeo/ptyx-mcq/commit/3ac1d999eb64b2c093abbb8e573cb15465074048))

- Enhance again the visual presentation of students' corrected assignments.
  ([`4468c5a`](https://github.com/wxgeo/ptyx-mcq/commit/4468c5a8b161f3fdf799c25902e7bb6f1961f592))

- Enhance the visual presentation of students' corrected assignments.
  ([`522c8b2`](https://github.com/wxgeo/ptyx-mcq/commit/522c8b2362c37e8e05b546eda50fa16825996043))

- Faster image extraction using mupdf.
  ([`00c63a8`](https://github.com/wxgeo/ptyx-mcq/commit/00c63a8d0eec2568ca6de6bc864096c372b9f600))

- New --debug option in CLI. Remove old --ask-for-name option.
  ([`51c0f9c`](https://github.com/wxgeo/ptyx-mcq/commit/51c0f9cf91fc3860067a8710dfffa999a32475bf))

- Stricter MCQ syntax, enabling better handling of verbatim mode.
  ([`226ea91`](https://github.com/wxgeo/ptyx-mcq/commit/226ea91ad009399870f6ac666857f91a34b3698b))

- Use "/" to skip a document when name is missing.
  ([`b24cc80`](https://github.com/wxgeo/ptyx-mcq/commit/b24cc807a9b3f3fc5839892d5bef1a54526f944c))

### Refactoring

- A bit more refactoring in `scan/scan_pic.py`.
  ([`debff54`](https://github.com/wxgeo/ptyx-mcq/commit/debff54435e2e791842743d3a6080336b7ca1229))

- Move away all user interaction from main scan pass. (Tests missing...)
  ([`9c50d50`](https://github.com/wxgeo/ptyx-mcq/commit/9c50d50854b1e3754c032413ce837cde0476a9e6))

- Move final data integrity verification to `ConflictSolver` class.
  ([`f83a69b`](https://github.com/wxgeo/ptyx-mcq/commit/f83a69be0b1824fbbcf5f7191ce9a05123efdec6))

- Rename some variables and functions.
  ([`5f6198a`](https://github.com/wxgeo/ptyx-mcq/commit/5f6198a437140bbc7ecfcc040f5c35f48311203a))

- Rename variables to conform to snake_case.
  ([`e20674d`](https://github.com/wxgeo/ptyx-mcq/commit/e20674da15533b4b4ac218a25bc8c749b584de7b))

- Split exercises parsing code in several functions.
  ([`df2f85a`](https://github.com/wxgeo/ptyx-mcq/commit/df2f85a7bca7b48374b287d8ed9532a8704cf07e))

### Testing

- Add data for a new test.
  ([`72e60b3`](https://github.com/wxgeo/ptyx-mcq/commit/72e60b3ed1dfe490a5e5511d3926cc63e9a068f3))

- Add tests for conflict resolution.
  ([`f395256`](https://github.com/wxgeo/ptyx-mcq/commit/f3952566a6bcadc2dd1a5ee1767077bda874d017))

- Add tests for duplicate pages conflict solver.
  ([`30045f6`](https://github.com/wxgeo/ptyx-mcq/commit/30045f6d1f486f81f6c5dcd10f58ed6c475feb60))

- All tests pass again.
  ([`732820b`](https://github.com/wxgeo/ptyx-mcq/commit/732820be5601c77b42f82a10a26dcd2e462b1a9b))

- Fix failing tests.
  ([`1ca01a1`](https://github.com/wxgeo/ptyx-mcq/commit/1ca01a1a3a1742f6cdcc95b005e4ae2c2ee28b6a))

- Fix some broken tests.
  ([`c729776`](https://github.com/wxgeo/ptyx-mcq/commit/c729776cf51961056f89ccf54ef45a02242f36d7))

- Improve cli tests.
  ([`605f1d7`](https://github.com/wxgeo/ptyx-mcq/commit/605f1d7fd11ecb7e6530aa636775b57578d4e849))

- New files for testing.
  ([`d787cb2`](https://github.com/wxgeo/ptyx-mcq/commit/d787cb21397e6288d33f30cd59ec645f43c90116))

- New test draft.
  ([`b0c822b`](https://github.com/wxgeo/ptyx-mcq/commit/b0c822b010d2f99e7a252744e0ae8a82edae1c75))


## v26.1.0 (2023-11-28)

### Features

- New function `get_template_path()`.
  ([`76b2b19`](https://github.com/wxgeo/ptyx-mcq/commit/76b2b1962c478955adcab4ec9b1388ca44ad6f79))


## v26.0.0 (2023-11-21)

### Bug Fixes

- Don't update config if questions or answers changed.
  ([`dc65271`](https://github.com/wxgeo/ptyx-mcq/commit/dc65271f6f64ec56f6f18939f1ef670ac8191809))

- Don't use ptyx.make_file() anymore, for compatibility with ptyx 27.0.0.
  ([`cac8e71`](https://github.com/wxgeo/ptyx-mcq/commit/cac8e716c29f594198d1c06e1a14e040039c6502))

- Fix `mcq-dev export-cheboxes` command.
  ([`a5bcaff`](https://github.com/wxgeo/ptyx-mcq/commit/a5bcaff18c21308cf5f000f081b779f72fd6508d))

- Fix some evaluation methods, and improve doc and tests.
  ([`6dd2e46`](https://github.com/wxgeo/ptyx-mcq/commit/6dd2e467cfbe2b12579ca4dedb3c3945a0d16d11))

- Quit when some included files are missing.
  ([`4c56ff7`](https://github.com/wxgeo/ptyx-mcq/commit/4c56ff7ae5527c83a5b7c20d938839c666311252))

### Build System

- Update poetry.lock
  ([`d7db3f3`](https://github.com/wxgeo/ptyx-mcq/commit/d7db3f323edaf59c07a6ea7a623b9a4b23c7f175))

### Features

- Change evaluation strategies.
  ([`ff68165`](https://github.com/wxgeo/ptyx-mcq/commit/ff68165c6acbacd006c66fcfcdd95ff5b0fdb77a))

- Implement header-free mode.
  ([`b48fb92`](https://github.com/wxgeo/ptyx-mcq/commit/b48fb924a0a4401969a2ba539600489b3ffca391))

- Improve bash completion.
  ([`ff99a6b`](https://github.com/wxgeo/ptyx-mcq/commit/ff99a6bfb043b339d6deb3634ee489f39e2661e5))

- Include LaTeX package amsmath bien default.
  ([`aaa7b69`](https://github.com/wxgeo/ptyx-mcq/commit/aaa7b69d4f3b9fd72a0b1f2a34baffbb860be204))

- Load packages asmsymb and colortbl by default.
  ([`70fa27f`](https://github.com/wxgeo/ptyx-mcq/commit/70fa27f906612c000471da4135efc9dc6f0fbb9e))

- New specific CLI for development.
  ([`9f61ee2`](https://github.com/wxgeo/ptyx-mcq/commit/9f61ee2c37fb6b48a1f104cf733ca7c8c948c266))

- Use ptyx 26.0.1+, which improve LaTeX errors display.
  ([`251d406`](https://github.com/wxgeo/ptyx-mcq/commit/251d40686a1043d3b10af70dce015a77dac7ea45))

- Use ptyx 27.0.0
  ([`239e853`](https://github.com/wxgeo/ptyx-mcq/commit/239e85363a911836ecc8e4d071dda6b911fb4ab2))

### Testing

- Change tests order in ruff.
  ([`0305666`](https://github.com/wxgeo/ptyx-mcq/commit/0305666206d1d5c97624a76f9db52a71d51caddf))

- Improve checkboxes export for generating tests. (Work in progress).
  ([`24c3d52`](https://github.com/wxgeo/ptyx-mcq/commit/24c3d529376ee20618ecd2c40b930640fdccddef))

- Replace flake8 with ruff.
  ([`19210fd`](https://github.com/wxgeo/ptyx-mcq/commit/19210fda60bfdcd8aac7b63f7f2ea7f57c6ae4d4))


## v25.0.0 (2023-10-17)

### Bug Fixes

- \usepackage[T1]{fontenc}
  ([`e1d663b`](https://github.com/wxgeo/ptyx-mcq/commit/e1d663bef74c798f008aabf3eeaf78b99bdc3e47))

- Fix regression in answers editing when some questions are not answsered.
  ([`0d72d6a`](https://github.com/wxgeo/ptyx-mcq/commit/0d72d6ab86e734a3381c44a11148b1506e5aa73a))

- Include directives outside of the mcq section are correctly handled now.
  ([`90b4aa9`](https://github.com/wxgeo/ptyx-mcq/commit/90b4aa999dfb6d2caf755e22ae83a05953f691e6))

### Build System

- Add a Makefile.
  ([`f99f6cd`](https://github.com/wxgeo/ptyx-mcq/commit/f99f6cdf4ddfdbc8f0a7f5dc7c1b5793cb736616))

- Update poetry.lock.
  ([`5b5c706`](https://github.com/wxgeo/ptyx-mcq/commit/5b5c70652c5e723817538ecc0c5d0abc2d889cc5))

- Use semantic versioning.
  ([`86433e5`](https://github.com/wxgeo/ptyx-mcq/commit/86433e560d63bfa05445c6cf6f19b3f95780c9a6))

### Features

- Add a review mode, with each exercise title displayed.
  ([`4c0ed63`](https://github.com/wxgeo/ptyx-mcq/commit/4c0ed63c33e2a20e3a775c967d3945b74ef0aa6d))

- Add support for completion in bash.
  ([`c8b06ad`](https://github.com/wxgeo/ptyx-mcq/commit/c8b06adab74f57a87ec179dd3ac0ab119a0b4c8f))

- Improve checkboxes analysis, and restore ability to fully resume scan.
  ([`8791acf`](https://github.com/wxgeo/ptyx-mcq/commit/8791acf713c09f3dd563443e1e18c2ffdc8fc571))

- Minor change in document header.
  ([`a05c5c7`](https://github.com/wxgeo/ptyx-mcq/commit/a05c5c77739090c46ded477d8997c8254b53778b))

- New syntax to include exercises, and new cli options to update includes.
  ([`25d280e`](https://github.com/wxgeo/ptyx-mcq/commit/25d280e1d4dccdcc534e5d0173705b6ac8deabe9))

### Performance Improvements

- A dry `mcq --help` command is now much faster.
  ([`22524a9`](https://github.com/wxgeo/ptyx-mcq/commit/22524a9d17f9e4f7e6f8e7a1ee8f6f3ddb7e6343))


## v22.3.1 (2023-01-24)

- Initial Release
