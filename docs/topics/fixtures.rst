Fixtures
========

.. autofunction:: saltfactories.plugins.event_listener::event_listener
   :noindex:

.. _configure-loader-modules-fixture:

``configure_loader_modules``
----------------------------

.. admonition:: Note

   The ``configure_loader_modules`` fixture is meant to be used on unit-tests, the ``pytest-salt-factories`` plugin
   does not define it anywhere. Instead, the user must define it on the test module.

The fixture **must** return a dictionary, where the keys are the salt modules that need to be patched, and the values
are dictionaries. These dictionaries should have the
:ref:`salt dunders <salt:dunder-dictionaries>` as keys. These dunders are dictionaries that the
salt loader injects at runtime, so, they are not available outside of Salt's runtime.
