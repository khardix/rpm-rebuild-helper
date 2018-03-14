Services
========

.. py:currentmodule:: rpmrh

The rpmrh tool is in essence just a sophisticated plumbing for processing of source RPMs.
In order to actually *do* anything with the packages, it uses a :term:`service`.
The service is usually some non-local RPM-handling tool, such as `Koji`_, but it could be anything that can take a source RPM package or meta-data and do something with it.

.. _Koji: https://pagure.io/koji
.. _Fedora Koji: https://koji.fedoraproject.org/
.. _CBS: https://cbs.centos.org

Internally, each service is represented by a class.
Instance(s) of that class (i.e. `Koji`_) directly corresponds to instance(s) of the service (i.e. `Fedora Koji`_ or `CBS`_).

Similar kinds of services share a common API, which is defined using dedicated :abbr:`ABC (Abstract Base Class)` s (see :py:mod:`abc` for details).
Currently, the recognized service kinds are :py:class:`.abc.Repository` and :py:class:`.abc.Builder`.

As for the services themselves, the currently supported are:

  * :py:class:`.service.Koji` (:py:class:`.abc.Repository` and :py:class:`.abc.Builder`) for interaction with `Koji`_ instances.
  * :py:class:`.service.DNF` (:py:class:`.abc.Repository`) for getting packages from regular package repositories.
  * :py:class:`.service.Jenkins`\ [#jenkins]_ for interaction with `Jenkins CI <https://jenkins.io/>`_.

Available instances of these services are defined by configuration files with extension ``.service.toml``.
In order to add a new service instance, just add it to :ref:`configuration`.
Example configuration of `CBS`_ (`Koji`_ instance), shipped with this package:

.. literalinclude:: ../rpmrh/conf.d/cbs.service.toml
   :language: ini

Each instance is defined by single configuration section.
The name of the section can be arbitrary string, but it should be unique, as it acts as the instance identification.
The only field required by each service is ``type``, which indicates the service (class) to use.

For possible values of the type field and other fields supported by each type see :py:mod:`.service` documentation.

Phases
======

During the rebuild process, a single RPM usually need to traverse multiple services before it's release.
In the example case of CentOS `SCLo SIG <https://wiki.centos.org/SpecialInterestGroup/SCLo>`_,
the package first need to be rebuild in `CBS`_, which automatically tags it into "candidate" tag,
and subsequently tested and tagged to "testing" and finally "release" tag.

The concept of :term:`phase`\ s abstracts these kind of processes.
Each phase defines a group of services available under a single name,
with the appropriate service chosen by the requested operation --- Repository for package queries, Builder for building, etc.

The phases are defined entirely by :ref:`configuration`, in files with extension ``.phase.toml``.
The configuration of phases for the SCLo SIG rebuild, shipped with this package:

.. literalinclude:: ../rpmrh/conf.d/sclo-sig.phase.toml
    :language: ini

This is a bit complicated, so let's break it apart.
Similar to service instances, each phase is defined by a configuration section -- for example ``sclo-testing``.
The section then can contain up to three subsections, labeled ``repo``, ``builder``, and ``check``.

.. note::

    The TOML syntax allows omission of "empty" super-sections, and that is why there is no explicit ``[sclo-testing]`` section header -- it is inferred from its subsections.
    For details, see `TOML README <https://github.com/toml-lang/toml>`_.

Each sub-section has this general structure:

.. code-block:: ini

    [<phase-name>.<kind>]
    service = <name of service instance to use>
    <package-groups> = [<list of group name formats>]

The service label indicates which service instance should be used by the phase for appropriate package operations.

The package groups are ``tags`` (for ``repo``, used for generic queries),
``targets`` (for ``builder``, used for package builds)
and ``tests`` (for ``check``, used for checking the package health)\ [#nomenclature]_\ .
Each takes a list of :py:func:`str.format` compatible format strings, which are used to generate the actual package group names used in the package operations.

Example phase
-------------

The theoretical description above is best illustrated with complete example.
Consider the ``sclo-testing`` phase:

.. literalinclude:: ../rpmrh/conf.d/sclo-sig.phase.toml
    :language: ini
    :lines: 15-24

This phase has two associated services: a ``cbs`` `Koji`_ instance, used as ``repo``, and ``ci.centos.org`` `Jenkins`_ instance; both of which are defined in separate ``.service.toml`` file (see above).

The ``repo`` part contains a ``tags`` field with the value ``['sclo{el}-{collection}-rh-testing']``.
This indicates to rpmrh that when querying for any package with the ``cbs`` instance,
it should generate a tag name from this format a query that tag
-- i.e. ``sclo7-rh-python36-rh-testing`` when querying for package in ``rh-python36`` SCL for CentOS 7.

The ``check`` part is very similar, apart from the fact that there are multiple formats in the ``tests`` field.
In this case, the results of all (both) matching test runs will be examined in order to determine package health.


.. rubric:: Footnotes

.. [#jenkins] The Jenkins service implementation is very specific to our test setup.
    Without comparison with alternative setup, a generic API definitions does not make sense.
    If you need more generic take on the test interface, your :abbr:`PR (Pull Request)` is welcome!
.. [#nomenclature] This names come from the `Koji`_ service, where "tags" describe a collection of available packages, and "targets" groups packages being built with the build environment.
