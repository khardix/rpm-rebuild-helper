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

Compare packages between two tags, to find out which packages in `rh-python36`
collection needs to be tested in CentoOS 7::

   rpmrh \
        --from sclo-candidate --to sclo-testing \
        --collection rh-python36 --el 7 \
        diff

Check which packages needs to be tested in all currently supported
(released and not End-Of-Life) collections for both CentOS 6 and 7::

    rpmrh --from sclo-candidate --to sclo-testing \
        --all-collections --el 6 --el 7 \
        diff
