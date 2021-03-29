======================
Install Salt Factories
======================

Installing Salt Factories is as simple as:

.. code-block:: bash

   python -m pip install pytest-salt-factories


And, that's honestly it.


Salt
====

Salt factories does not define |salt| as a hard requirement because that would create a chicken and egg problem while
testing Salt itself.
This is not a problem while testing code outside of the |saltrepo|.

To install |salt| along with Salt Factories:

.. code-block:: bash

   python -m pip install 'pytest-salt-factories[salt]'



Docker
======

Salt factories also supports container factories using docker containers.
To have container support enabled, install Salt Factories along with docker:

.. code-block:: bash

   python -m pip install 'pytest-salt-factories[docker]'



Multiple Optional Dependencies
==============================

Installing salt-factories with multiple optional dependencies is also simple.

.. code-block:: bash

   python -m pip install 'pytest-salt-factories[salt,docker]'
