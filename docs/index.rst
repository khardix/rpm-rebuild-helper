#########################
rpmrh: RPM Rebuild Helper
#########################

Version: |version|

.. image:: https://img.shields.io/pypi/v/rpmrh.svg
.. image:: https://img.shields.io/pypi/l/rpmrh.svg
.. image:: https://img.shields.io/pypi/pyversions/rpmrh.svg
.. image:: https://img.shields.io/pypi/status/rpmrh.svg

.. |rpmrh| replace:: ``rpmrh``

The RPM Rebuild Helper (|rpmrh| for short) is an automation tool for batch rebuilding of existing RPM packages.
It focuses primarily on `Software Collections`_ packages in order to make lives easier for `CentOS SCLo SIG`_.

.. _Software Collections: https://www.softwarecollections.org
.. _CentOS SCLo SIG: https://wiki.centos.org/SpecialInterestGroup/SCLo

Usage examples
--------------

Determine packages missing from CentOS testing repository::

    $ rpmrh --from sclo-candidate --to sclo-testing --all-collections diff

Tag to release all tested packages for specific (``rh-python36``) software collection::

    $ rpmrh --from sclo-testing --to sclo-release --collection rh-python36 \
        diff --min-days=7 tested tag

See :doc:`quickstart` and :doc:`manual page <man/rpmrh>` for further details.

User Guide
----------

.. toctree::
    :maxdepth: 2

    installation
    quickstart
    concepts
    man/index
