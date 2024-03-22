.. _changelog:

=========
Changelog
=========

Versions follow `Semantic Versioning <https://semver.org>`_ (`<major>.<minor>.<patch>`).

Backward incompatible (breaking) changes will only be introduced in major versions with advance notice in the
**Deprecations** section of releases.

.. admonition:: Previous Changelog Entries
   :class: attention

   Before the 1.0.0 release, due to the fast evolving pace and breakage introduced while developing the library,
   no changelog was kept. Please refer to the git history for details.


.. towncrier-draft-entries::

.. towncrier release notes start

1.0.1 (2024-03-22)
==================

Bug Fixes
---------

- Properly configure the SSHD server when FIPS is enabled/enforced on a system (`#179 <https://github.com/saltstack/pytest-salt-factories/issues/179>`_)


1.0.0 (2024-03-21)
==================

Improvements
------------

- The `SSHD` daemon implementation now has a `get_host_keys` method which returns the host keys that can then be written to a ``known_hosts`` file. (`#176 <https://github.com/saltstack/pytest-salt-factories/issues/176>`_)


Trivial/Internal Changes
------------------------

- CI pipeline changes:

  * Stop testing against Pytest 8.0.0rc2 and instead test against 8.0.x
  * Stop testing against Salt 3005.x
  * Add Salt 3007.x to the versions to test
  * Stop testing against Pytest 7.3.x and add 8.1.x to the list of versions to test (`#177 <https://github.com/saltstack/pytest-salt-factories/issues/177>`_)


1.0.0rc29 (2024-01-23)
======================

Improvements
------------

- Add ``--sys-info-and-exit`` which basically prints the system information and exit. Doesn't run any tests. (`#173 <https://github.com/saltstack/pytest-salt-factories/issues/173>`_)


Trivial/Internal Changes
------------------------

- Switch pipelines to use Python 3.11 and start testing Pytest 8.0.0rc2 (`#173 <https://github.com/saltstack/pytest-salt-factories/issues/173>`_)


1.0.0rc28 (2023-11-25)
======================

Features
--------

- Added a containarized salt master class implementation, ``SaltMaster`` (`#169 <https://github.com/saltstack/pytest-salt-factories/issues/169>`_)


Improvements
------------

- Switch to testing against Salt 3006.x instead of 3005.x (`#169 <https://github.com/saltstack/pytest-salt-factories/issues/169>`_)


Bug Fixes
---------

- The ``Container._pull_container`` callback now properly registers on the ``SaltMinion`` and the ``SaltMaster`` classes when ``pull_before_start`` is True (`#168 <https://github.com/saltstack/pytest-salt-factories/issues/168>`_)


Improved Documentation
----------------------

- Fix the readthedocs builds due to https://blog.readthedocs.com/migrate-configuration-v2/ (`#169 <https://github.com/saltstack/pytest-salt-factories/issues/169>`_)


1.0.0rc27 (2023-09-27)
======================

Bug Fixes
---------

- Allow the Salt engine to run on Python 3.6 (`#167 <https://github.com/saltstack/pytest-salt-factories/issues/167>`_)


1.0.0rc26 (2023-09-20)
======================

Bug Fixes
---------

- Check if path exists before running additional checks on the `temp_directory` context manager. (`#160 <https://github.com/saltstack/pytest-salt-factories/issues/160>`_)
- The ``container`` implementation is now sensible to the ``exited`` state when starting containers. (`#165 <https://github.com/saltstack/pytest-salt-factories/issues/165>`_)


Improved Documentation
----------------------

- Updated documentation for SaltEnv temp_file and added an example usage (`#163 <https://github.com/saltstack/pytest-salt-factories/issues/163>`_)


1.0.0rc25 (2023-07-31)
======================

Improvements
------------

- Remove `pytest-tempdir` package dependency (`#154 <https://github.com/saltstack/pytest-salt-factories/issues/154>`_)
- Stop using deprecated `@pytest.mark.trylast` (`#155 <https://github.com/saltstack/pytest-salt-factories/issues/155>`_)
- Simplify and reduce the amount of patching required to unit test loader modules (`#156 <https://github.com/saltstack/pytest-salt-factories/issues/156>`_)


Trivial/Internal Changes
------------------------

- Some internal processes improvements:

  * Publish packages to PyPi with trusted publishers
  * Enable dependabot to update the GH Actions versions on a weekly basis (`#151 <https://github.com/saltstack/pytest-salt-factories/issues/151>`_)
- Start using actionlint and shellcheck to validate GH Actions workflows (`#153 <https://github.com/saltstack/pytest-salt-factories/issues/153>`_)
- Improve code coverage by either removing code not getting used anymore or marking sections of the code which are not expected to be covered (`#157 <https://github.com/saltstack/pytest-salt-factories/issues/157>`_)


1.0.0rc24 (2023-07-27)
======================

Improvements
------------

- Several improvements to reduce failure points:

  * Log the exception instead of raising it.
  * Always populate the `*_dirs` config settings, regardless of how salt-factories is being used
  * Improved the connect/disconnect behavior of the event listener client
  * The minimum supported Salt version is now 3005.0
  * The minimum supported Pytest version is now 7.0.0 (`#149 <https://github.com/saltstack/pytest-salt-factories/issues/149>`_)


Bug Fixes
---------

- Do not blindly overwrite the `retuner_address` configuration key (`#146 <https://github.com/saltstack/pytest-salt-factories/issues/146>`_)


Trivial/Internal Changes
------------------------

- Start checking the code base with ruff (`#149 <https://github.com/saltstack/pytest-salt-factories/issues/149>`_)


1.0.0rc23 (2022-12-15)
======================

Bug Fixes
---------

- Fixed Salt's deferred imports to allow onedir builds while not breaking non-onedir builds:

  * Additionally, stopped relying on `salt.utils.files` and `salt.utils.yaml`
  * Stopped using `zmq` to forward events(this was where the breakage was showing) for a plain TCP implementation.
  * The `event_listener` fixture is now started/stopped like a regular pytest fixture
  * The `event_listener` server now restarts in case something goes wrong to the point where it crashes. (`#146 <https://github.com/saltstack/pytest-salt-factories/issues/146>`_)


1.0.0rc22 (2022-12-02)
======================

Breaking Changes
----------------

- Drop support for Python 3.5 and 3.6 (`#123 <https://github.com/saltstack/pytest-salt-factories/issues/123>`_)


Improvements
------------

- Defer all `salt` imports so that we can use pytest-salt-factories to test onedir builds (`#144 <https://github.com/saltstack/pytest-salt-factories/issues/144>`_)
- A few improvements to functional testing support:

  * Allow `StateReturn` to be accessed by key instead of just attribute
  * Add warning for when more than a state function is used under the same state key
  * Return an instance of `MatchString` for `StateResult.comment` (`#145 <https://github.com/saltstack/pytest-salt-factories/issues/145>`_)


Trivial/Internal Changes
------------------------

- Update the github actions versions to avoid deprecation errors (`#145 <https://github.com/saltstack/pytest-salt-factories/issues/145>`_)


1.0.0rc21 (2022-11-04)
======================

Improvements
------------

- Several improvements to the state module wrappers:

  * Allow getting the state chunk by `__id__` on MultiStateResult
  * Wrap a few more functions from `salt.modules.state` (`#140 <https://github.com/saltstack/pytest-salt-factories/issues/140>`_)


Trivial/Internal Changes
------------------------

- Pipeline and requirements fixes:

  * Test against 3005.* and not 3005rc2 since it's now released.
  * Install `importlib-metadata<5.0.0` since only Salt>=3006 will be able to handle it (`#140 <https://github.com/saltstack/pytest-salt-factories/issues/140>`_)


1.0.0rc20 (2022-08-25)
======================

Bug Fixes
---------

- The `spm` CLI now properly lays down the configuration files required (`#137 <https://github.com/saltstack/pytest-salt-factories/issues/137>`_)


1.0.0rc19 (2022-08-22)
======================

Breaking Changes
----------------

- In `saltfactories.utils.cli_scipts.generate_script()`:

  * For coverage tracking, both `coverate_db_path` and `coverage_rc_path` must be passed. They will not be infered by `root_dir`.
  * `inject_coverage` was removed. (`#135 <https://github.com/saltstack/pytest-salt-factories/issues/135>`_)
- The minimum Salt version in now `3004` (`#136 <https://github.com/saltstack/pytest-salt-factories/issues/136>`_)


Trivial/Internal Changes
------------------------

- CI and internal changes:

  * Start testing Salt 3005.x (rc2 for now)
  * Skip testing 3005rc2 on windows and macOS for now.
  * Lock system tests to a version of nox that still works
  * Bump python version to 3.9 for lint workflow
  * Bumped pylint requirement to `2.14.5` and cleaned up issues
  * Don't build the salt minion container during test runs, pull an existing container. (`#136 <https://github.com/saltstack/pytest-salt-factories/issues/136>`_)


1.0.0rc18 (2022-07-14)
======================

Breaking Changes
----------------

- Renamed the ``system_install`` configuration flag, markers and behaviours when set to ``system_service`` to better reflect what it's actually used for. (`#96 <https://github.com/saltstack/pytest-salt-factories/issues/96>`_)


Features
--------

- Allow passing ``--python-executable`` to teak which python get's used to prefix CLI commands, when needed. (`#129 <https://github.com/saltstack/pytest-salt-factories/issues/129>`_)
- Allow passing ``--scripts-dir`` to tell salt-factories where to look for the Salt daemon and CLI scripts.
  The several scripts to the Salt daemons and CLI's **must** exist. Also, passing this option will additionally make
  salt-factories **NOT** generate said scripts and set ``python_executable`` to ``None`` (`#130 <https://github.com/saltstack/pytest-salt-factories/issues/130>`_)
- Added CLI support(``--system-service``) to change salt-factories to use Salt previously installed from the platform's package manager. (`#131 <https://github.com/saltstack/pytest-salt-factories/issues/131>`_)
- Inject ``engines_dirs`` and ``log_handlers_dirs`` when ``system_service=True`` or ``scripts_path`` is not ``None``
  These flags suggest that the salt being imported and used by salt-factories might not be the same as the one being tested.
  So, in this case, make sure events and logging from started daemons still get forwarded to salt-factories. (`#133 <https://github.com/saltstack/pytest-salt-factories/issues/133>`_)


1.0.0rc17 (2022-06-17)
======================

Bug Fixes
---------

- Bump deprecations targeted for 2.0.0 to 3.0.0 (`#122 <https://github.com/saltstack/pytest-salt-factories/issues/122>`_)
- Try to pass ``loaded_base_name`` to each of Salt's loaders used in our ``Loaders`` class, if not supported, patch it at runtime. (`#126 <https://github.com/saltstack/pytest-salt-factories/issues/126>`_)
- ``saltfactories.utils.warn_until()`` is now aware of Pytest's rewrite calls and properly reports the offending code. (`#127 <https://github.com/saltstack/pytest-salt-factories/issues/127>`_)


1.0.0rc16 (2022-05-28)
======================

Improvements
------------

- Switch to internal start check ``callables``.

  Additionally, significant container improvements, like:

  * Get host ports to check from the container port bindings.
  * Always terminate the containers.
  * Support randomly assigned host port bindings

  ``skip_on_salt_system_install`` is now also a marker provided by ``pytest-salt-factories``. (`#120 <https://github.com/saltstack/pytest-salt-factories/issues/120>`_)


1.0.0rc15 (2022-05-09)
======================

Improvements
------------

- Now that the new logging changes are merged into Salt's master branch, adjust detection of those changes on ``SaltKey``. (`#118 <https://github.com/saltstack/pytest-salt-factories/issues/118>`_)


Bug Fixes
---------

- ``--timeout`` is now correctly passed for CLI factories when either ``timeout`` is defined on the configuration or when ``timeout`` is passed to the CLI factory constructor. (`#117 <https://github.com/saltstack/pytest-salt-factories/issues/117>`_)


Trivial/Internal Changes
------------------------

- Test PyTest 7.0.x and 7.1.x & Fix tests requirements

  * Don't allow ``pytest-subtests`` to upgrade pytest
  * Test under PyTest 7.0.x and 7.1.x
  * Force Jinja2 to be < 3.1 on Salt 3003.x
  * Fix the requirements of the example ``echo-extension``
  * Explicitly pass a timeout to Salt CLI's on spawning platforms.
  * Windows builds were not getting passed the ``PYTEST_VERSION_REQUIREMENT`` env var. (`#116 <https://github.com/saltstack/pytest-salt-factories/issues/116>`_)


1.0.0rc14 (2022-04-06)
======================

Bug Fixes
---------

- Fixed container tests not passing on macOS (`#114 <https://github.com/saltstack/pytest-salt-factories/issues/114>`_)


Trivial/Internal Changes
------------------------

- Pin click on the black pre-commit hooks (`#115 <https://github.com/saltstack/pytest-salt-factories/issues/115>`_)


1.0.0rc13 (2022-03-28)
======================

Bug Fixes
---------

- Handle docker client initialization error on macOS. (`#113 <https://github.com/saltstack/pytest-salt-factories/issues/113>`_)


1.0.0rc12 (2022-03-27)
======================

Bug Fixes
---------

- Catch ``APIError`` when removing containers (`#112 <https://github.com/saltstack/pytest-salt-factories/issues/112>`_)


1.0.0rc11 (2022-03-22)
======================

Improvements
------------

- Provide a ``SECURITY.md`` file for the project (`#67 <https://github.com/saltstack/pytest-salt-factories/issues/67>`_)
- It's no longer necessary to pass a docker client instance as ``docker_client`` when using containers. (`#111 <https://github.com/saltstack/pytest-salt-factories/issues/111>`_)


1.0.0rc10 (2022-03-21)
======================

Improvements
------------

- The docker container daemon now pulls the image by default prior to starting it. (`#109 <https://github.com/saltstack/pytest-salt-factories/issues/109>`_)


Bug Fixes
---------

- Provide backwards compatibility imports for the old factory exceptions, now in pytest-shell-utilities (`#108 <https://github.com/saltstack/pytest-salt-factories/issues/108>`_)
- Base classes for the ``SaltDaemon`` containers order is now fixed. (`#110 <https://github.com/saltstack/pytest-salt-factories/issues/110>`_)


1.0.0rc9 (2022-03-20)
=====================

Improvements
------------

- Use old-style Salt entrypoints for improved backwards compatibility. (`#98 <https://github.com/saltstack/pytest-salt-factories/issues/98>`_)


1.0.0rc8 (2022-03-12)
=====================

Bug Fixes
---------

- Instead of just removing `saltfactories.utils.ports` and `saltfactories.utils.processes`, redirect the imports to the right library and show a deprecation warning. (`#106 <https://github.com/saltstack/pytest-salt-factories/issues/106>`_)


1.0.0rc7 (2022-02-19)
=====================

Bug Fixes
---------

- The containers factory does not accept the ``stats_processes`` keyword. (`#105 <https://github.com/saltstack/pytest-salt-factories/issues/105>`_)


1.0.0rc6 (2022-02-17)
=====================

Bug Fixes
---------

- Include the started daemons in the ``stats_processes`` dictionary (`#104 <https://github.com/saltstack/pytest-salt-factories/issues/104>`_)


1.0.0rc5 (2022-02-17)
=====================

Improvements
------------

- Wipe the ``cachedir`` for on each ``saltfactories.utils.functional.Loaders`` reset (`#103 <https://github.com/saltstack/pytest-salt-factories/issues/103>`_)


1.0.0rc4 (2022-02-17)
=====================

Bug Fixes
---------

- Properly handle missing keys in the configuration for the pytest salt logging handler. (`#101 <https://github.com/saltstack/pytest-salt-factories/issues/101>`_)
- Fix passing ``--timeout`` to Salt's CLI's (`#102 <https://github.com/saltstack/pytest-salt-factories/issues/102>`_)


1.0.0rc3 (2022-02-16)
=====================

Bug Fixes
---------

- Fix ``pathlib.path`` typo (`#99 <https://github.com/saltstack/pytest-salt-factories/issues/99>`_)
- Fixed issue with ``sdist`` recompression for reproducible packages not iterating though subdirectories contents. (`#100 <https://github.com/saltstack/pytest-salt-factories/issues/100>`_)


1.0.0rc2 (2022-02-14)
=====================

Improvements
------------

- Improve documentation (`#92 <https://github.com/saltstack/pytest-salt-factories/issues/92>`_)


Bug Fixes
---------

- Fix issue where, on system installations, the minion ID on the configuration, if not explicitly passed on ``overrides`` or ``defaults``, would default to the master ID used to create the salt minion factory. (`#93 <https://github.com/saltstack/pytest-salt-factories/issues/93>`_)
- Allow configuring ``root_dir`` in ``setup_salt_factories`` fixture (`#95 <https://github.com/saltstack/pytest-salt-factories/issues/95>`_)


0.912.2 (2022-02-14)
====================

Bug Fixes
---------

- Use salt's entry-points instead of relying on loader ``*_dirs`` configs (`#98 <https://github.com/saltstack/pytest-salt-factories/issues/98>`_)


0.912.1 (2022-02-05)
====================

Improvements
------------

- Set lower required python version to 3.5.2 (`#97 <https://github.com/saltstack/pytest-salt-factories/issues/97>`_)


1.0.0rc1 (2022-01-27)
=====================

Breaking Changes
----------------

- Switch to the extracted pytest plugins

  * Switch to pytest-system-statistics
  * Switch to pytest-shell-utilities (`#90 <https://github.com/saltstack/pytest-salt-factories/issues/90>`_)


0.912.0 (2022-01-25)
====================

Breaking Changes
----------------

- `Name things once <https://www.youtube.com/watch?v=1__lNTlj1_w>`_. (`#50 <https://github.com/saltstack/pytest-salt-factories/issues/50>`_)
- ``get_unused_localhost_port`` no longer cached returned port by default (`#51 <https://github.com/saltstack/pytest-salt-factories/issues/51>`_)
- Rename the ``SaltMaster.get_salt_cli`` to ``SaltMaster.salt_cli``, forgotten on `PR #50 <https://github.com/saltstack/pytest-salt-factories/pull/50>`_ (`#70 <https://github.com/saltstack/pytest-salt-factories/issues/70>`_)


Features
--------

- Temporary state tree management

  *  Add ``temp_file`` and ``temp_directory`` support as pytest helpers
  *  Add ``SaltStateTree`` and ``SaltPillarTree`` for easier temp files support (`#38 <https://github.com/saltstack/pytest-salt-factories/issues/38>`_)
- Added skip markers for AArch64 platform, ``skip_on_aarch64`` and ``skip_unless_on_aarch64`` (`#40 <https://github.com/saltstack/pytest-salt-factories/issues/40>`_)
- Added a ``VirtualEnv`` helper class to create and interact with a virtual environment (`#43 <https://github.com/saltstack/pytest-salt-factories/issues/43>`_)
- Add ``skip_on_spawning_platform`` and ``skip_unless_on_spawning_platform`` markers (`#81 <https://github.com/saltstack/pytest-salt-factories/issues/81>`_)


Improvements
------------

- Switch project to an ``src/`` based layout (`#41 <https://github.com/saltstack/pytest-salt-factories/issues/41>`_)
- Start using `towncrier <https://pypi.org/project/towncrier/>`_ to maintain the changelog (`#42 <https://github.com/saltstack/pytest-salt-factories/issues/42>`_)
- Forwarding logs, file and pillar roots fixes

  * Salt allows minions and proxy minions to also have file and pillar roots configured
  * All factories will now send logs of level ``debug`` or higher to the log server (`#49 <https://github.com/saltstack/pytest-salt-factories/issues/49>`_)
- Log the test outcome (`#52 <https://github.com/saltstack/pytest-salt-factories/issues/52>`_)
- Take into account that ``SystemExit.code`` might not be an integer on the generated CLI scripts (`#62 <https://github.com/saltstack/pytest-salt-factories/issues/62>`_)
- Catch unhandled exceptions and write their traceback to ``sys.stderr`` in the generated CLI scripts (`#63 <https://github.com/saltstack/pytest-salt-factories/issues/63>`_)
- Several fixes/improvements to the ``ZMQHandler`` log forwarding handler (`#64 <https://github.com/saltstack/pytest-salt-factories/issues/64>`_)
- ZMQ needs to reconnect on forked processes or else Salt's own multiprocessing log forwarding log records won't be logged by the ``ZMQHandler`` (`#69 <https://github.com/saltstack/pytest-salt-factories/issues/69>`_)
- Some more additional changes to the ZMQHandler to make sure it's resources are cleaned when terminating (`#74 <https://github.com/saltstack/pytest-salt-factories/issues/74>`_)
- The ``sshd`` server no longer generates ``dsa`` keys if the system has FIPS enabled (`#80 <https://github.com/saltstack/pytest-salt-factories/issues/80>`_)
- Add ``to_salt_config`` method to ``SaltEnv`` and ``SaltEnvs``. This will simplify augmenting the salt configuration dictionary. (`#82 <https://github.com/saltstack/pytest-salt-factories/issues/82>`_)
- Rename ``SaltEnv.to_salt_config()`` to ``SaltEnv.as_dict()`` (`#83 <https://github.com/saltstack/pytest-salt-factories/issues/83>`_)
- Switch to `pytest-skip-markers <https://pypi.org/project/pytest-skip-markers>`_. (`#84 <https://github.com/saltstack/pytest-salt-factories/issues/84>`_)


Bug Fixes
---------

- Adjust to the upcoming salt loader changes (`#77 <https://github.com/saltstack/pytest-salt-factories/issues/77>`_)


Trivial/Internal Changes
------------------------

- CI pileline adjustements

  * Bump salt testing requirement to 3002.6
  * Drop testing of FreeBSD since it's too unreliable on Github Actions
  * Full clone when testing so that codecov does not complain (`#39 <https://github.com/saltstack/pytest-salt-factories/issues/39>`_)
- Upgrade to black 21.4b2 (`#56 <https://github.com/saltstack/pytest-salt-factories/issues/56>`_)
- Drop Pytest requirement to 6.0.0 (`#57 <https://github.com/saltstack/pytest-salt-factories/issues/57>`_)
- Increase and match CI system tests `timeout-minutes` to Linux tests `timeout-minutes` (`#64 <https://github.com/saltstack/pytest-salt-factories/issues/64>`_)
- Switch to the `new codecov uploader <https://about.codecov.io/blog/introducing-codecovs-new-uploader>`_ (`#72 <https://github.com/saltstack/pytest-salt-factories/issues/72>`_)
- Fix codecov flags, report name, and coverage (`#73 <https://github.com/saltstack/pytest-salt-factories/issues/73>`_)
- Update to latest versions on some pre-commit hooks

  * ``pyupgrade``: 2.23.3
  * ``reorder_python_imports``: 2.6.0
  * ``black``: 21.b7
  * ``blacken-docs``: 1.10.0 (`#79 <https://github.com/saltstack/pytest-salt-factories/issues/79>`_)
- Remove ``transport`` keyword argument from the call to ``salt.utils.event.get_event`` (`#87 <https://github.com/saltstack/pytest-salt-factories/issues/87>`_)
- Add ``build`` and ``release`` nox targets (`#89 <https://github.com/saltstack/pytest-salt-factories/issues/89>`_)
