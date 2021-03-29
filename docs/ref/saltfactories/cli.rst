=============================
``salt-factories`` CLI Script
=============================

The ``salt-factories`` CLI script is meant to be used to get an absolute path to the directory containing
``sitecustomize.py`` so that it can be injected into ``PYTHONPATH`` when running tests to track subprocesses
code coverage.

Example:

.. code-block:: bash

    export PYTHONPATH="$(salt-factories --coverage);$PYTHONPATH"

Please check the :ref:`coverage documentation <coverage:subprocess>` on the additional requirements
to track code coverage on subprocesses.
