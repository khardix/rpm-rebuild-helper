rpmrh
=====

Synopsis
--------

**rpmrh** [*options*] [<*command*> [*options*] ...]

Description
-----------

:program:`rpmrh` is a CLI toolkit for automation of RPM package rebuilds between various providers.
The main focus of this program is the continuous rebuilding of `RPM Software Collections`_.

.. _RPM Software Collections: https://www.softwarecollections.org

.. todo::

    Describe what *service* and *phase* means.
    Point user to detailed documentation.

Global Options
^^^^^^^^^^^^^^

.. program:: rpmrh

.. option:: --help

    Print program help and exit.

.. option:: -q, --quiet

    Silence the informative output (info logging, progress, etc.)

.. option:: -f <FROM_PHASE>, --from=<FROM_PHASE>

    Select source phase.

    This option may be required depending on the selected subcommand.

.. option:: -t <TO_PHASE>, --to=<TO_PHASE>

    Same as :option:`-f`, but select the target phase.

.. option:: -c <COLLECTION>, --collection=<COLLECTION>

    Select the Software Collection to be processed.
    Can be specified multiple times to process multiple collections.
    Use :option:`--all-collections` for automatic selection of all known collections.

.. option:: --all-collections, --all

    Automatically selects all non-EOL collections to process.

.. option:: -e <VERSION>, --el=<VERSION>

    Select which Enterprise Linux (EL) version of selected collections should be processed.
    Can be specified multiple times to select multiple EL versions.

.. option:: -i <FILE>, --input=<FILE>

    Path to YAML file with input data.
    Use ``-`` for stadard input.

.. option:: --report=<FILE>

    Write results to *FILE*.
    If not specified, the results are written to standard output.

Subcommands
-----------

These subcommands drive the processing itself.
Each subcommand can be used alone and in sequence with others.
When sequenced, output of previous subcommand is taken as input of the next one (similar to UNIX pipes).

diff
^^^^

Compares packages present in repositories (tags) of source and target phases.

Input
    List of collections to compare. Any package metadata are discarded.

Output
    Set of packages from source phase missing in target phase.

*Options*

.. program:: rpmrh diff

.. option:: --min-days=<N>

    Restrict the comparison only to packages which were added to source repository at least *N* days ago.

.. option:: --simple-dist, --no-simple-dist

    Turn the simplification of dist tag comparisons on (default) or off.
    When turned on, only major dist version are considered;
    for example, ``.el7_4`` is considered equivalent with ``.el7``.

download
^^^^^^^^

Download source packages (SRPMs) to specified directory.

Input
    Set of package metadata to download for each collection.

Output
    Set of paths to downloaded SRPMs for each collection.

*Options*

.. program:: rpmrh download

.. option:: -d <DIR>, --output-dir=<DIR>

    Output directory for the downloaded SRPMs.
    If not specified, current directory will be used.

build
^^^^^

Attempt to build packages from local SRPMs using target phase builder.

Input
    Set of paths to local SRPMs to build for each collection.

Output
    Set of package metadata of successful builds for each collection.

*Options*

.. program:: rpmrh build

.. option:: -f <FILE>, --failed=<FILE>

    Store report of build failures in FILE.
    If not specified, use standard error output.

tag
^^^

Add packages to a target repository tag.

Input
    Set of package metadata to tag for each collection.

Output
    Set of successfully tagged package metadata for each collection.

*Options*

.. program:: rpmrh tag

.. option:: --owner=<NAME>

    Use NAME as the owner for new packages in the target tag.

.. todo:: What happens if owner is not specified? Config.

Files
-----

:file:`$XDG_CONFIG_HOME/rpmrh/config.toml`
    Main :program:`rpmrh` configuration file.
    See :manpage:`rpmrh-config(5)` for details.

:file:`$XDG_CONFIG_HOME/rpmrh/{name}.service.toml`, :file:`$XDG_CONFIG_HOME/rpmrh/{name}.phase.toml`
    Configuration files with :term:`service`\ s or :term:`phase`\ s definitions, respectively.
    See :manpage:`rpmrh-config(5)` for details.
