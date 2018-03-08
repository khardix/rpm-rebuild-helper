Installation instructions
=========================

.. _rpm: http://rpm.org
.. _koji: https://pagure.io/koji/
.. _dnf: https://github.com/rpm-software-management/dnf

The rpmrh package is `available from PyPI <https://pypi.python.org>`_.
However, it depends on several Python libraries *not* available from there,
namely `rpm`_, `koji`_ and `dnf`_.
These need to be installed separately by your distribution package manager.
For example, this command installs the dependencies on Fedora 27::

    $ sudo dnf install python3-rpm python3-koji python3-dnf

After that, use ``pip`` to install the package itself::

    $ python3 -m pip install --user rpmrh
