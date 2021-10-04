=======
Markers
=======

Salt factories ships with a few markers, skip markers.
Additional markers used in Salt's test suite are provided by the `skip-markers`_ pytest plugin.

.. _skip-markers: https://pypi.org/project/pytest-skip-markers

.. _markers.requires_salt_modules:

``requires_salt_modules``
=========================

.. py:decorator:: pytest.mark.requires_salt_modules(*modules)

    :param str modules:
      Each argument passed to the marker should be a :ref:`salt execution module <salt:all-salt.modules>` that
      will need to be loaded by salt, or the test will be skipped.
      Allowed values are the module name, for example ``cmd``, or the module name with the function name,
      ``cmd.run``.

    .. code-block:: python

        @pytest.mark.requires_salt_modules("cmd", "archive.tar")
        def test_func():
            assert True



.. _markers.requires_salt_states:

``requires_salt_states``
========================

.. py:decorator:: pytest.mark.requires_salt_states(*modules)

    :param str modules:
      Each argument passed to the marker should be a :ref:`salt state module <salt:all-salt.states>` that
      will need to be loaded by salt, or the test will be skipped.
      Allowed values are the state module name, for example ``pkg``, or the state module name with the function name,
      ``pkg.installed``.

    .. code-block:: python

        @pytest.mark.requires_salt_states("pkg", "archive.extracted")
        def test_func():
            assert True
