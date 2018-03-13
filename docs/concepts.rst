Services
========

.. py:currentmodule:: rpmrh

The rpmrh tool is in essence just a sofisticated plumbing for processing of source RPMs.
In order to actually *do* anything with the packages, it uses a :term:`service`.
The service is usually some non-local RPM-handling tool, such as `Koji`_, but it could be anything that can take a source RPM package or metadata and do something with it.

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


.. rubric:: Footnotes

.. [#jenkins] The Jenkins service implementation is very specific to our test setup.
    Without comparison with alternative setup, a generic API definitions does not make sense.
    If you need more generic take on the test interface, your :abbr:`PR (Pull Request)` is welcome!
