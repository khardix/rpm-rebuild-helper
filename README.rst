RPM Rebuild Helper
==================

The RPM Rebuild Helper (or `rpmrh` for short)
is an automation tool for rebuilding sets of (S)RPM files.
Its main focus are `Software Collections <https://softwarecollections.org>`_.

The tool allows the user to compare two sets of RPMs,
download and modify the respective SRPMs locally
and automatically rebuild them in a build service,
among other things.

Usage example
-------------

Compare released packages between two build services
-- Fedora's Koji and CentOS CBS --
for a `python34` software collection::

   rpmrh diff --from koji --to cbs --collection python34

Or for all currently active (released and not End-of-Life) collections::

   rpmrh diff --all --from koji --to cbs

Attempt to automatically rebuild all missing packages::

   rpmrh rebuild --from koji --to cbs --all
