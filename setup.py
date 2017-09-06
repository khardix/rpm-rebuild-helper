#!/usr/bin/env python3

from pathlib import Path
from setuptools import setup, find_packages

METADATA = {
    'name': 'rpmrh',
    'use_scm_version': True,
    'description':
        'An automation tool for rebuilding RPMs and Software Collections',
    'long_description':
        Path(__file__).with_name('README.rst').read_text('utf-8'),
    'url':
        'https://github.com/khardix/rpm-rebuild-helper',
    'author': 'Jan Staněk',
    'author_email': 'jstanek@redhat.com',

    'license': 'GPLv3+',
    'classifiers': [
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',  # noqa: E501

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    'keywords': 'rpm scl softwarecollections rebuilding'
}

DEPENDENCIES = [
    'attrs>=17',
    'cerberus',
    'click',
    'PyTrie',
    'requests',
    'requests-file',
    'toml',
    'pyxdg',
]

TEST_DEPENDENCIES = [  # only for pytest-runner!
    'pytest',
    'betamax',
    'pyfakefs',
]

SETUP_DEPENDENCIES = [
    'setuptools_scm',
    'pytest-runner>=2.0,<3dev',
]

EXTRA_DEPENDECIES = {
}

setup(
    **METADATA,
    setup_requires=SETUP_DEPENDENCIES,
    install_requires=DEPENDENCIES,
    tests_require=TEST_DEPENDENCIES,
    extras_require=EXTRA_DEPENDECIES,
    packages=find_packages(exclude={'tests', 'docs', 'service'}),
    package_data={
        'rpmrh': [
            'conf.d/*.service.toml',  # Included service configurations
        ],
    },
    entry_points={
        'console_scripts': [
            'rpmrh=rpmrh.cli:main',
        ],
    },
)
