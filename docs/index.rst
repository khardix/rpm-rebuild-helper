#########################
rpmrh: RPM Rebuild Helper
#########################

Version: |version|

.. image:: https://img.shields.io/pypi/v/rpmrh.svg
.. image:: https://img.shields.io/pypi/l/rpmrh.svg
.. image:: https://img.shields.io/pypi/pyversions/rpmrh.svg
.. image:: https://img.shields.io/pypi/status/rpmrh.svg
.. image:: https://img.shields.io/readthedocs/rpm-rebuild-helper.svg

.. |rpmrh| replace:: ``rpmrh``

The RPM Rebuild Helper (|rpmrh| for short) is an automation tool for batch rebuilding of existing RPM packages.
It focuses primarily on `Software Collections`_ packages in order to make lives easier for `CentOS SCLo SIG`_.

.. _Software Collections: https://www.softwarecollections.org
.. _CentOS SCLo SIG: https://wiki.centos.org/SpecialInterestGroup/SCLo

.. contents::

Usage examples
--------------

Determine packages missing from CentOS testing repository::

    $ rpmrh --from sclo-candidate --to sclo-testing --all-collections diff

Tag to release all tested packages for specific (``rh-python36``) software collection::

    $ rpmrh --from sclo-testing --to sclo-release --collection rh-python36 \
        diff --min-days=7 tested tag

Consult the :doc:`man page <man/rpmrh>` for detailed description of the command-line usage.

Installation
------------

.. _rpm: http://rpm.org
.. _koji: https://pagure.io/koji/
.. _dnf: https://github.com/rpm-software-management/dnf

The rpmrh package is `available from PyPI <https://pypi.org/project/rpmrh/>`_.
However, it depends on several Python libraries *not* available from there, namely `rpm`_, `koji`_ and `dnf`_.
These need to be installed separately by your distribution package manager.
For example, this command installs the dependencies on Fedora 27 and later::

    $ sudo dnf install python3-rpm python3-koji python3-dnf

After that, use ``pip`` to install the package itself::

    $ python3 -m pip install --user rpmrh

Configuration
-------------

|rpmrh| looks for configuration files in :file:`$XDG_CONFIG_HOME/rpmrh` (falling back to :file:`~/.config/rpmrh` if :envvar:`XDG_CONFIG_HOME` is not defined).
There are two kinds of configuration files: :file:`{name}.service.toml` and :file:`{name}.phase.toml`, both of which are expected to be in the `TOML <https://github.com/toml-lang/toml>`_ language.

.. _Jenkins: https://jenkins.io/
.. _sclo-ci-tests: https://github.com/sclorg/sclo-ci-tests

Service
=======

The :file:`{name}.service.toml` describes a *service*.
A service can be anything that could be queried or instructed to work with RPM packages.
Currently supported kinds of services are `dnf`_ repositories, `koji`_ instances and a `Jenkins`_ instance running tests from `sclo-ci-tests`_ repository.
Each configuration file can contain multiple service configurations, each described by a single section (dictionary)::

    [cbs]
    type = 'koji'
    profile_name = 'cbs'

    ['ci.centos.org']
    type = 'jenkins'
    url = 'https://ci.centos.org'

The mandatory parts are the service name (section name) and the ``type`` key, which determines the kind of service to configure.
Other attributes are passed as keyword arguments to the constructor of the underlying Python object; see :doc:`API docs <api/service>` for the supported configuration values.

Phase
=====

A *phase* groups services together, and indicates that they are interconnected in some way.
For example, it can indicate that packages built by ``cbs`` service are tested by ``ci.centos.org`` service::

    [sclo-candidate.repo]   # Used for package queries
    service = 'cbs'
    tags = ['sclo{el}-{collection}-rh-candidate']

    [sclo-candidate.build]  # Used for building new packages
    service = 'cbs'
    targets = ['sclo{el}-{collection}-rh-el{el}']

    [sclo-candidate.check]  # Used for querying test results
    service = 'ci.centos.org'
    tests = ['SCLo-pkg-{collection}-rh-C{el}-candidate-x86_64']

Each phase can have up to three sub-sections:

#.  ``repo``, which indicates that it's ``service`` should be used for retrieving existing packages.
#.  ``build``, which designates the ``service`` responsible for handling rebuilds.
#.  ``check``, which indicates that the ``service`` runs test over existing packages.

Each sub-section than should be configured with appropriate package group selection:

#.  ``tags`` designates which packages should be queried; it is interpreted as `koji`_ tag name or a concrete repository from `dnf`_ repository group.
#.  ``targets`` lists the `koji`_ targets to which the packages should be built.
#.  ``tests`` select which `Jenkins`_ jobs are taken as relevant to the health of any given package.

The group selection can optionally contain ``{collection}`` and/or ``{el}`` placeholders.
These are dynamically replaced for each processed package by the appropriate SCL name and major EPEL version, respectivelly.

Manual Pages
------------

.. toctree::
   :maxdepth: 2

   man/rpmrh

API Documentation
-----------------

.. toctree::
   :maxdepth: 3

   api/rpm
   api/service
