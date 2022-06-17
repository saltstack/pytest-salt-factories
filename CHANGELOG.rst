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
