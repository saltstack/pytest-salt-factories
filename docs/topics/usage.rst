====================
Using Salt Factories
====================

Salt factories simplifies testing |salt| related code outside of Salt's source tree.
A great example is a |salt-extension|.


Let's consider this ``echo-extension`` example.

The ``echo-extension`` provides an execution module:

.. include-example:: examples/echo-extension/src/echoext/modules/echo_mod.py

And also a state module:

.. include-example:: examples/echo-extension/src/echoext/states/echo_mod.py

One could start off with something simple like unit testing the extension's code.


Unit Tests
==========

.. include-example:: examples/echo-extension/tests/unit/modules/test_echo.py
.. include-example:: examples/echo-extension/tests/unit/states/test_echo.py

The *magical* piece of code in the above example is the :ref:`configure-loader-modules-fixture` fixture.


Integration Tests
=================

.. include-example:: examples/echo-extension/tests/conftest.py
.. include-example:: examples/echo-extension/tests/integration/conftest.py
.. include-example:: examples/echo-extension/tests/integration/modules/test_echo.py
.. include-example:: examples/echo-extension/tests/integration/states/test_echo.py


What happened above?

1. We started a salt master
2. We started a salt minion
3. The minion connects to the master
4. The master accepted the minion's key automatically
5. We pinged the minion

.. admonition:: A litle suggestion

   Not all tests should be integration tests, in fact, only a small set of the
   test suite should be an integration test.
