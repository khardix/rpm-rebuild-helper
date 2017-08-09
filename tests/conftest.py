"""py.test configuration and shared fixtures"""

import os
from contextlib import ExitStack, closing
from itertools import chain, repeat
from operator import itemgetter
from pathlib import Path
from subprocess import run
from textwrap import dedent

import betamax
import pytest

import createrepo_c as crc


# Betamax configuration
CASSETTE_DIR = Path('tests/cassettes/')
CASSETTE_DIR.mkdir(exist_ok=True)

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = str(CASSETTE_DIR)
    config.default_cassette_options.update({
        'record_mode': 'none' if os.environ.get('TRAVIS_BUILD') else 'once',
        'preserve_exact_body_bytes': True,
    })


# Fixtures

@pytest.fixture(scope='module')
def minimal_spec_contents():
    """Text contents of a minimal SPEC file."""

    return dedent('''\
        %{?scl:%scl_package test}
        %{!?scl:%global pkg_name %{name}}

        Name:       %{?scl_prefix}test
        Version:    1.0
        Release:    1%{?dist}
        Summary:    Minimal spec for testing purposes

        Group:      Development/Testing
        License:    MIT
        URL:        http://test.example.com

        %description
        A minimal SPEC file for testing of RPM packaging.

        %prep
        %build
        %install
        %files

        %changelog
        * Thu Jun 22 2017 Jan Stanek <jstanek@redhat.com> 1.0-1
        - Initial package
    ''')


@pytest.fixture(scope='module')
def minimal_spec_path(tmpdir_factory, minimal_spec_contents):
    """Provide a minimal SPEC file in a temporary directory."""

    tmpdir = tmpdir_factory.mktemp('rpmbuild')

    path = Path(str(tmpdir), 'test.spec')
    path.write_text(minimal_spec_contents)

    return path


@pytest.fixture(scope='module')
def minimal_srpm_path(minimal_spec_path):
    """Provide a minimal source RPM in a temporary directory."""

    top_dir = minimal_spec_path.parent

    # rpmbuild setup
    defines = chain.from_iterable(
        ('--define', '_{kind}dir {top_dir}'.format(kind=kind, top_dir=top_dir))
        for kind in ['top', 'source', 'spec', 'build', 'srcrpm', 'rpm']
    )

    run(['rpmbuild'] + list(defines) + ['-bs', str(minimal_spec_path)])

    return next(top_dir.glob('test-*.src.rpm'))


@pytest.fixture(scope='module')
def minimal_repository_url(minimal_srpm_path):
    """Provide a minimal complete YUM/DNF repository."""

    # Adapted from https://github.com/rpm-software-management/createrepo_c/blob/master/examples/python/simple_createrepo.py  # noqa: E501

    root_dir = minimal_srpm_path.parent
    repodata = root_dir / 'repodata'
    repodata.mkdir(exist_ok=True)

    # Order matters!
    db_setup = [  # DB file name -> DB initializer
        ('primary.sqlite', crc.PrimarySqlite),
        ('filelists.sqlite', crc.FilelistsSqlite),
        ('other.sqlite', crc.OtherSqlite),
    ]

    xml_setup = [  # XML file name -> XML initializer
        ('primary.xml.gz', crc.PrimaryXmlFile),
        ('filelists.xml.gz', crc.FilelistsXmlFile),
        ('other.xml.gz', crc.OtherXmlFile),
    ]

    with ExitStack() as repo_setup:
        # Open sqlite databases
        db_stack = repo_setup.enter_context(ExitStack())
        databases = [
            db_stack.enter_context(closing(init(str(repodata / name))))
            for name, init in db_setup
        ]

        # Open XML files
        xml_stack = repo_setup.enter_context(ExitStack())
        xml_files = [
            xml_stack.enter_context(closing(init(str(repodata / name))))
            for name, init in xml_setup
        ]

        # Get all rpm in the repo directory
        pkg_list = list(root_dir.glob('*.rpm'))

        # Process the packages
        for xfile in xml_files:
            xfile.set_num_of_pkgs(len(pkg_list))

        for pkg_path in pkg_list:
            pkg = crc.package_from_rpm(str(pkg_path))
            pkg.location_href = pkg_path.name

            for db in xml_files + databases:
                db.add_pkg(pkg)

        xml_stack.close()

        # Create metadata file
        record_keys = [
            'primary', 'filelists', 'other',
            'primary_db', 'filelists_db', 'other_db',
        ]
        record_paths = map(itemgetter(0), xml_setup + db_setup)
        record_dbs = chain(databases, repeat(None))
        record_params = zip(record_keys, record_paths, record_dbs)

        metadata = crc.Repomd()
        for key, path, db_to_update in record_params:
            record = crc.RepomdRecord(key, str(repodata / path))
            record.fill(crc.SHA256)

            if db_to_update:
                db_to_update.dbinfo_update(record.checksum)

            metadata.set_record(record)

        db_stack.close()

        with (repodata / 'repomd.xml').open(mode='w') as ostream:
            ostream.write(metadata.xml_dump())

    return 'file://{}/'.format(repodata.parent.resolve())
