"""py.test configuration and shared fixtures"""

from itertools import chain
from pathlib import Path
from subprocess import run
from textwrap import dedent

import pytest


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
